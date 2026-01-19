# sidecar/actions_store.py
import logging
import time
import sqlite3
from bridge.db.database import get_db

log = logging.getLogger("sidecar.actions.store")

def persist_action(action: dict):
    """
    Persist AI-decided action exactly once.

    action schema:
    {
        message_id, platform, room_id,
        label, action, confidence
    }
    """
    db = get_db()
    now = int(time.time())

    try:
        with db:
            db.execute("""
                INSERT INTO actions (
                    message_id,
                    platform,
                    room_id,
                    label,
                    action,
                    confidence,
                    state,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 'PENDING', ?)
            """, (
                action["message_id"],
                action["platform"],
                action["room_id"],
                action["label"],
                action["action"],
                action["confidence"],
                now,
            ))
        return True

    except sqlite3.IntegrityError:
        log.info(
            "Duplicate action ignored by DB",
            extra={
                "message_id": action["message_id"],
                "action": action["action"],
                "platform": action["platform"],
            }
        )
        return False