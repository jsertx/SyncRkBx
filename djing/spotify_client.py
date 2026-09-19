"""Lectura de playlists de Spotify (Client Credentials flow, solo lectura)."""

import re

import spotipy
from spotipy.oauth2 import SpotifyOAuth

_PLAYLIST_URL_RE = re.compile(r"playlist[/:]([a-zA-Z0-9]+)")

SCOPE = "playlist-read-private playlist-read-collaborative"


def build_client(client_id: str, client_secret: str, redirect_uri: str) -> spotipy.Spotify:
    """Authorization Code flow: hace falta login de usuario (una vez, luego cachea el token)
    porque las playlists privadas/colaborativas no son accesibles con Client Credentials."""
    auth = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=SCOPE,
        cache_path=".spotify_token_cache",
    )
    return spotipy.Spotify(auth_manager=auth)


def resolve_playlist_id(value: str) -> str:
    """Acepta una URL de Spotify, un URI (spotify:playlist:ID) o un ID pelado."""
    match = _PLAYLIST_URL_RE.search(value)
    if match:
        return match.group(1).split("?")[0]
    return value


def get_playlist_name(sp: spotipy.Spotify, playlist_id: str) -> str:
    playlist = sp.playlist(playlist_id, fields="name")
    return playlist["name"]


def get_playlist_tracks(sp: spotipy.Spotify, playlist_id: str) -> list[dict]:
    """Devuelve [{title, artists}] para cada track disponible de la playlist."""
    tracks: list[dict] = []
    results = sp.playlist_items(playlist_id, additional_types=["track"])

    while results:
        for entry in results["items"]:
            # La API devuelve el track bajo "track" normalmente, pero algunas
            # respuestas lo anidan bajo "item" en su lugar.
            track = entry.get("track") or entry.get("item")
            if not track or track.get("is_local"):
                continue
            title = track.get("name")
            artists = [a["name"] for a in track.get("artists", [])]
            if not title or not artists:
                continue
            tracks.append({"title": title, "artists": artists})

        results = sp.next(results) if results.get("next") else None

    return tracks
