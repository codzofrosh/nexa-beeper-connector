"""Cursor store used by the bridge to persist the last processed timestamp.

This module provides a tiny durable cursor so the executor can continue
processing from where it left off after restarts.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "cursor.db"


def _get_conn():
    return sqlite3.connect(DB_PATH, isolation_level=None)


def init_cursor():
    """Ensure cursor table exists and initialize if absent."""
    with _get_conn() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS cursor (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            last_ts INTEGER NOT NULL
        )
        """)
        cur = conn.execute("SELECT last_ts FROM cursor WHERE id = 1")
        if cur.fetchone() is None:
            conn.execute(
                "INSERT INTO cursor (id, last_ts) VALUES (1, 0)"
            )


def load_cursor() -> int:
    """Return the last stored timestamp (cursor)."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT last_ts FROM cursor WHERE id = 1"
        ).fetchone()
        return row[0]


def advance_cursor(new_ts: int):
    """Update the stored cursor to `new_ts`."""
    with _get_conn() as conn:
        conn.execute(
            "UPDATE cursor SET last_ts = ? WHERE id = 1",
            (new_ts,)
        )
