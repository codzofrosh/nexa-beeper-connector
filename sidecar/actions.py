"""Persistence helpers for actions stored by the sidecar.

This module provides a small CRUD-style interface to the `actions` table
used by the sidecar and bridge executor logic. `publish` is used by the
worker to insert an action if it is new (idempotent insert).
"""

from typing import List
from sidecar.db import get_conn, init_db
from sidecar.models import ActionResult

init_db()

def publish(action: ActionResult) -> bool:
    """
    Returns True if inserted, False if duplicate
    """
    conn = get_conn()
    try:
        conn.execute("""
            INSERT OR IGNORE INTO actions
            (message_id, platform, room_id, label, action, confidence, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            action.message_id,
            action.platform,
            action.room_id,
            action.label,
            action.action,
            action.confidence,
            action.timestamp
        ))
        conn.commit()
        return conn.total_changes == 1
    finally:
        conn.close()

def fetch(limit: int = 100) -> List[ActionResult]:
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT * FROM actions
            ORDER BY timestamp ASC
            LIMIT ?
        """, (limit,)).fetchall()

        return [ActionResult(**dict(r)) for r in rows]
    finally:
        conn.close()

def fetch_since(ts: int, limit: int = 100) -> List[ActionResult]:
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT * FROM actions
            WHERE timestamp > ?
            ORDER BY timestamp ASC
            LIMIT ?
        """, (ts, limit)).fetchall()

        return [ActionResult(**dict(r)) for r in rows]
    finally:
        conn.close()
