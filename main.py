#!/usr/bin/env python3
"""Orquestador: Spotify -> Soulseek (slskd) -> Rekordbox.

Uso:
    python3 main.py [config.json]

IMPORTANTE: cierra Rekordbox antes de ejecutar (pyrekordbox escribe en master.db).
"""

import sys

from djing import rekordbox_sync, spotify_client
from djing.config import load_config
from djing.soulseek_client import SlskdClient, pick_best_result
from djing.tracker import Tracker


def sync_playlist(sp, slskd, tracker, cfg, playlist_ref: str) -> None:
    playlist_id = spotify_client.resolve_playlist_id(playlist_ref)
    playlist_name = spotify_client.get_playlist_name(sp, playlist_id)
    tracks = spotify_client.get_playlist_tracks(sp, playlist_id)

    print(f"\n=== Playlist: '{playlist_name}' ({len(tracks)} tracks) ===")

    downloaded = 0
    already_had = 0
    failed = []

    for track in tracks:
        title = track["title"]
        artists_str = ", ".join(track["artists"])

        status = tracker.get_status(playlist_id, title, artists_str)
        if status == "downloaded":
            already_had += 1
            continue

        query = f"{artists_str} {title}"
        print(f"  buscando: {query}")

        best = None
        for attempt_query in (query, title):
            results = slskd.search(attempt_query, cfg.search_timeout_seconds)
            best = pick_best_result(results, title, track["artists"], cfg.allowed_extensions)
            if best:
                break

        if not best:
            print("    sin resultados válidos")
            tracker.mark_failed(playlist_id, title, artists_str)
            failed.append(query)
            continue

        try:
            slskd.download(best)
            ok = slskd.wait_for_download(best["username"], best["filename"])
        except Exception as e:
            print(f"    ERROR descargando: {e}")
            ok = False

        if ok:
            print(f"    descargado: {best['filename']}")
            tracker.mark_downloaded(playlist_id, title, artists_str, best["filename"])
            downloaded += 1
        else:
            print("    descarga falló o expiró el tiempo de espera")
            tracker.mark_failed(playlist_id, title, artists_str)
            failed.append(query)

    print(
        f"  Resumen '{playlist_name}': {downloaded} descargada(s), "
        f"{already_had} ya estaban, {len(failed)} fallida(s)."
    )
    if failed:
        print("  No conseguidas:")
        for q in failed:
            print(f"    - {q}")

    print("  Sincronizando con Rekordbox...")
    rekordbox_sync.copy_new_mp3s(cfg.download_folder, cfg.library_folder)

    db = rekordbox_sync.open_database()
    try:
        rekordbox_sync.sync_rekordbox_playlist(db, cfg.library_folder, playlist_name)
        db.commit()
    finally:
        db.close()


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    cfg = load_config(config_path)

    print("Cierra Rekordbox antes de continuar (escribir en master.db con Rekordbox abierto puede corromperlo).")

    sp = spotify_client.build_client(
        cfg.spotify_client_id, cfg.spotify_client_secret, cfg.spotify_redirect_uri
    )
    slskd = SlskdClient(cfg.slskd_host, cfg.slskd_api_key)
    tracker = Tracker()

    try:
        for playlist_ref in cfg.sync_playlists:
            sync_playlist(sp, slskd, tracker, cfg, playlist_ref)
    finally:
        tracker.close()


if __name__ == "__main__":
    main()
