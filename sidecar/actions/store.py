# sidecar/actions/store.py
import logging
import time
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
            int(time.time()),
        ))
        db.commit()
        return True # Inserted successfully
    except Exception as e:
        # UNIQUE(message_id, action) violation lands here
        log.info(
            "duplicate action ignored: %s",
            action["message_id"]
        )


