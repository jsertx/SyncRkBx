"""Carga y valida config.json."""

import json
import sys
from pathlib import Path
from typing import Any


class Config:
    def __init__(self, data: dict[str, Any]):
        self._data = data

        self.spotify_client_id: str = data["spotify"]["client_id"]
        self.spotify_client_secret: str = data["spotify"]["client_secret"]
        self.spotify_redirect_uri: str = data["spotify"].get(
            "redirect_uri", "http://127.0.0.1:8888/callback"
        )

        self.slskd_host: str = data["slskd"]["host"].rstrip("/")
        self.slskd_api_key: str = data["slskd"]["api_key"]

        soulseek = data.get("soulseek", {})
        self.search_timeout_seconds: float = soulseek.get("search_timeout_seconds", 8)
        self.max_retries: int = soulseek.get("max_retries", 2)
        self.allowed_extensions: set[str] = {
            ext.lower() for ext in soulseek.get("allowed_extensions", [".mp3"])
        }

        self.download_folder = Path(data["paths"]["download_folder"]).expanduser().resolve()
        self.library_folder = Path(data["paths"]["library_folder"]).expanduser().resolve()

        self.sync_playlists: list[str] = data["syncPlaylists"]


def load_config(path: str = "config.json") -> Config:
    config_path = Path(path)
    if not config_path.exists():
        print(f"ERROR: no existe {config_path}. Copia config.example.json -> config.json y rellénalo.")
        sys.exit(1)

    try:
        data = json.loads(config_path.read_text())
    except json.JSONDecodeError as e:
        print(f"ERROR: {config_path} no es JSON válido: {e}")
        sys.exit(1)

    try:
        return Config(data)
    except KeyError as e:
        print(f"ERROR: falta la clave {e} en {config_path}")
        sys.exit(1)
