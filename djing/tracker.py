"""SQLite: recuerda qué tracks ya se intentaron para no re-buscar/re-descargar."""

import sqlite3
from contextlib import closing
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS track_attempts (
    playlist_id TEXT NOT NULL,
    title TEXT NOT NULL,
    artists TEXT NOT NULL,
    status TEXT NOT NULL,       -- 'downloaded' | 'failed'
    filename TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (playlist_id, title, artists)
);
"""


class Tracker:
    def __init__(self, db_path: str = "djing.db"):
        self.conn = sqlite3.connect(Path(db_path))
        self.conn.execute(_SCHEMA)
        self.conn.commit()

    def get_status(self, playlist_id: str, title: str, artists: str) -> str | None:
        with closing(self.conn.cursor()) as cur:
            cur.execute(
                "SELECT status FROM track_attempts WHERE playlist_id=? AND title=? AND artists=?",
                (playlist_id, title, artists),
            )
            row = cur.fetchone()
            return row[0] if row else None

    def mark_downloaded(self, playlist_id: str, title: str, artists: str, filename: str) -> None:
        self._upsert(playlist_id, title, artists, "downloaded", filename)

    def mark_failed(self, playlist_id: str, title: str, artists: str) -> None:
        self._upsert(playlist_id, title, artists, "failed", None)

    def _upsert(self, playlist_id: str, title: str, artists: str, status: str, filename: str | None) -> None:
        self.conn.execute(
            """
            INSERT INTO track_attempts (playlist_id, title, artists, status, filename, updated_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(playlist_id, title, artists)
            DO UPDATE SET status=excluded.status, filename=excluded.filename, updated_at=excluded.updated_at
            """,
            (playlist_id, title, artists, status, filename),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
