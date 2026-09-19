"""Cliente REST para slskd: busca y descarga ficheros de Soulseek."""

import time

import requests
from rapidfuzz import fuzz

MIN_MATCH_SCORE = 55
_TERMINAL_SUCCESS_STATES = {"Completed, Succeeded"}
_TERMINAL_FAILURE_MARKERS = ("Errored", "Cancelled", "Rejected")


class SlskdClient:
    def __init__(self, host: str, api_key: str):
        self.host = host.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"X-API-Key": api_key})

    def _url(self, path: str) -> str:
        return f"{self.host}/api/v0{path}"

    def search(self, query: str, timeout_s: float) -> list[dict]:
        """Lanza una búsqueda y espera a que termine (o al timeout), devuelve ficheros planos."""
        resp = self._post_with_backoff("/searches", {"searchText": query})
        search_id = resp["id"]

        deadline = time.monotonic() + timeout_s
        completed = False
        while time.monotonic() < deadline:
            state = self.session.get(self._url(f"/searches/{search_id}")).json()
            if state.get("isComplete"):
                completed = True
                break
            time.sleep(0.5)

        if not completed:
            # No terminó a tiempo: hay que pararla explícitamente antes de leer/borrar,
            # si no sigue escribiendo resultados en background y el DELETE posterior
            # provoca un DbUpdateConcurrencyException en slskd que dejaba búsquedas
            # siguientes atascadas en 'Queued'.
            self.session.put(self._url(f"/searches/{search_id}"))

        responses = self.session.get(self._url(f"/searches/{search_id}/responses")).json()

        files = []
        for user_response in responses:
            username = user_response.get("username")
            for f in user_response.get("files", []):
                files.append(
                    {
                        "username": username,
                        "filename": f["filename"],
                        "size": f["size"],
                        "bitRate": f.get("bitRate") or 0,
                        "queueLength": user_response.get("queueLength", 0),
                        "hasFreeUploadSlot": user_response.get("hasFreeUploadSlot", False),
                    }
                )

        try:
            self.session.delete(self._url(f"/searches/{search_id}"))
        except requests.RequestException:
            pass
        return files

    def _post_with_backoff(self, path: str, body: dict, attempts: int = 5) -> dict:
        for attempt in range(attempts):
            resp = self.session.post(self._url(path), json=body)
            if resp.status_code == 429:
                time.sleep(1 + attempt)
                continue
            resp.raise_for_status()
            return resp.json()
        resp.raise_for_status()
        return resp.json()

    def download(self, result: dict) -> None:
        username = result["username"]
        body = [{"filename": result["filename"], "size": result["size"]}]
        resp = self.session.post(self._url(f"/transfers/downloads/{username}"), json=body)
        resp.raise_for_status()

    def wait_for_download(
        self, username: str, filename: str, poll_interval: float = 2.0, max_wait: float = 120.0
    ) -> bool:
        """Sondea hasta que la descarga termina. Devuelve True si se completó."""
        deadline = time.monotonic() + max_wait
        while time.monotonic() < deadline:
            resp = self.session.get(self._url(f"/transfers/downloads/{username}"))
            if resp.ok:
                for directory in resp.json().get("directories", []):
                    for f in directory.get("files", []):
                        if f.get("filename") != filename:
                            continue
                        state = f.get("state", "")
                        if state in _TERMINAL_SUCCESS_STATES:
                            return True
                        if any(marker in state for marker in _TERMINAL_FAILURE_MARKERS):
                            return False
            time.sleep(poll_interval)
        return False


def pick_best_result(
    results: list[dict], title: str, artists: list[str], allowed_extensions: set[str]
) -> dict | None:
    """Elige el mejor resultado por fuzzy match de nombre + bitrate + disponibilidad."""
    query = f"{' '.join(artists)} {title}".lower()

    candidates = [r for r in results if _extension_of(r["filename"]) in allowed_extensions]
    if not candidates:
        return None

    best = None
    best_score = -1.0

    for r in candidates:
        name_score = fuzz.token_set_ratio(query, _basename_no_ext(r["filename"]).lower())
        if name_score < MIN_MATCH_SCORE:
            continue

        score = name_score
        score += min(r["bitRate"], 320) / 320 * 10  # hasta +10 por bitrate
        score += 5 if r["hasFreeUploadSlot"] else 0
        score -= min(r["queueLength"], 50) / 50 * 5  # hasta -5 por cola larga

        if score > best_score:
            best_score = score
            best = r

    return best


def _extension_of(filename: str) -> str:
    normalized = filename.replace("\\", "/")
    if "." not in normalized:
        return ""
    return "." + normalized.rsplit(".", 1)[-1].lower()


def _basename_no_ext(filename: str) -> str:
    basename = filename.replace("\\", "/").rsplit("/", 1)[-1]
    return basename.rsplit(".", 1)[0] if "." in basename else basename
