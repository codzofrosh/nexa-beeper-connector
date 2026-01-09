"""Lightweight SQLite helpers for the sidecar.

Contains `get_conn()` and `init_db()` used by modules that persist
and read actions. The DB uses simple sqlite3 connections and a global
lock for schema setup.
"""

import sqlite3
import threading
from pathlib import Path

_DB_PATH = Path("sidecar_actions.db")
_LOCK = threading.Lock()

def get_conn():
    conn = sqlite3.connect(
        _DB_PATH,
        check_same_thread=False
    )
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with _LOCK:
        conn = get_conn()
        conn.execute("""
        CREATE TABLE IF NOT EXISTS actions (
            message_id TEXT PRIMARY KEY,
            platform TEXT NOT NULL,
            room_id TEXT NOT NULL,
            label TEXT NOT NULL,
            action TEXT NOT NULL,
            confidence REAL NOT NULL,
            timestamp INTEGER NOT NULL
        )
        """)
        conn.commit()
        conn.close()
