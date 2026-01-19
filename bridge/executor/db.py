"""DB helpers used by the bridge executor.

These helpers implement claiming/locking semantics for actions so multiple
executors can run concurrently and avoid races.
"""

from typing import Optional
import time
from bridge.executor.identity import EXECUTOR_ID
from bridge.executor.retry import MAX_ATTEMPTS, backoff_seconds
from sidecar import db

def fetch_candidate(db):
    return db.execute("""
        SELECT *
        FROM actions
        WHERE state IN ('PENDING', 'FAILED')
        ORDER BY created_at
        LIMIT 1
    """).fetchone()

def claim_next_action(db, now: int):
    row = fetch_candidate(db)
    if not row:
        return None

    # 🔒 BACKOFF ENFORCEMENT (THIS IS THE KEY)
    if row["state"] == "FAILED":
        delay = backoff_seconds(row)
        last = row["executed_at"] or row["created_at"]

        if now - last < delay:
            return None  # ⛔ too early, skip quietly

    # attempt atomic claim
    updated = db.execute("""
        UPDATE actions
        SET
            state = 'EXECUTING',
            claimed_at = ?,
            executor_id = ?
        WHERE id = ?
          AND state = ?
    """, (
        now,
        EXECUTOR_ID,
        row["id"],
        row["state"],
    ))

    if updated.rowcount != 1:
        return None  # lost race safely

    return db.execute(
        "SELECT * FROM actions WHERE id = ?",
        (row["id"],)
    ).fetchone()


def mark_done(db, action_id: int, now: int):
    """Mark an action as done if it is currently EXECUTING."""
    db.execute("""
        UPDATE actions
        SET state = 'DONE',
            executed_at = ?
        WHERE id = ?
          AND state = 'EXECUTING'
    """, (now, action_id))
    db.commit()


def recover_stuck_actions(db, now: int, timeout: int = 60, max_attempts: int = 5):
   db.execute("""
        UPDATE actions
        SET
            state = 'FAILED',
            executor_id = NULL,
            claimed_at = NULL
        WHERE state = 'EXECUTING'
          AND claimed_at < ?
    """, (now - timeout,))
   db.commit()

def mark_failed(db, action_id: int, error: str, now: int):
    db.execute("""
        UPDATE actions
        SET
            state = CASE
                WHEN attempts + 1 >= ? THEN 'DEAD'
                ELSE 'FAILED'
            END,
            attempts = attempts + 1,
            last_error = ?,
            executed_at = ?
        WHERE id = ?
          AND state = 'EXECUTING'
    """, (MAX_ATTEMPTS, error, now, action_id))
    db.commit()

def set_external_id(db, action_id: int, external_id: str, now: int) -> bool:
    cur = db.execute("""
        UPDATE actions
        SET external_id = ?,
            state = 'EXECUTING',
            claimed_at = ?
        WHERE id = ?
          AND external_id IS NULL
    """, (external_id, now, action_id))

    db.commit()
    return cur.rowcount == 1
