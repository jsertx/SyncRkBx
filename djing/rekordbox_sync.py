"""Copia mp3s descargados y los sincroniza con una playlist de Rekordbox.

Lógica portada de soulseek_to_rekordbox/sync_soulseek_to_rekordbox.py.
"""

import os
import shutil
import sys
from pathlib import Path

EXTENSIONS = {".mp3"}


def find_audio_files(folder: Path):
    for root, _dirs, files in os.walk(folder):
        for name in files:
            if Path(name).suffix.lower() in EXTENSIONS:
                yield Path(root) / name


def unique_dest_path(dest_folder: Path, filename: str) -> Path:
    stem, suffix = Path(filename).stem, Path(filename).suffix
    i = 1
    while True:
        candidate = dest_folder / f"{stem} ({i}){suffix}"
        if not candidate.exists():
            return candidate
        i += 1


def copy_new_mp3s(dl_folder: Path, dest_folder: Path) -> int:
    dest_folder.mkdir(parents=True, exist_ok=True)
    copied = 0
    skipped = 0

    for src in find_audio_files(dl_folder):
        dest = dest_folder / src.name
        if dest.exists():
            try:
                same_size = dest.stat().st_size == src.stat().st_size
            except OSError:
                same_size = False
            if same_size:
                skipped += 1
                continue
            dest = unique_dest_path(dest_folder, src.name)

        shutil.copy2(src, dest)
        copied += 1
        print(f"  copiado: {src.name}  ->  {dest.name}")

    print(f"Copia terminada: {copied} nuevo(s), {skipped} omitido(s) (ya existían).")
    return copied


def sync_rekordbox_playlist(db, dest_folder: Path, playlist_name: str) -> None:
    """Usa una conexión `Rekordbox6Database` ya abierta (no hace commit/close)."""
    playlist = db.get_playlist(Name=playlist_name).one_or_none()
    if playlist is None:
        playlist = db.create_playlist(playlist_name)
        print(f"Playlist creada en Rekordbox: '{playlist_name}'")
    else:
        print(f"Usando playlist existente: '{playlist_name}'")

    ids_en_playlist = {song.ContentID for song in playlist.Songs}

    added_to_collection = 0
    added_to_playlist = 0
    already_ok = 0

    mp3_files = sorted(p for p in dest_folder.glob("*.mp3"))

    for mp3 in mp3_files:
        path_str = str(mp3.resolve())

        content = db.get_content(FolderPath=path_str).one_or_none()
        if content is None:
            content = db.add_content(path_str)
            added_to_collection += 1
            print(f"  + añadido a la colección de Rekordbox: {mp3.name}")

        if content.ID not in ids_en_playlist:
            db.add_to_playlist(playlist, content)
            ids_en_playlist.add(content.ID)
            added_to_playlist += 1
            print(f"  + añadido a la playlist: {mp3.name}")
        else:
            already_ok += 1

    print(
        f"Rekordbox sincronizado: {added_to_collection} nuevo(s) en la colección, "
        f"{added_to_playlist} nuevo(s) en la playlist, {already_ok} ya estaban."
    )


def open_database():
    try:
        from pyrekordbox import Rekordbox6Database
    except ImportError:
        print("ERROR: falta la librería 'pyrekordbox'. Instálala con: pip3 install pyrekordbox")
        sys.exit(1)

    return Rekordbox6Database()
