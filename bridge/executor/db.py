"""DB helpers used by the bridge executor.

These helpers implement claiming/locking semantics for actions so multiple
executors can run concurrently and avoid races.
"""

from typing import Optional
import time
from bridge.executor.identity import EXECUTOR_ID


def claim_next_action(db, now: int, max_attempts: int = 5):
    """
    Atomically claim the next retryable action.
    """
    with db:
        row = db.execute("""
            SELECT id
            FROM actions
            WHERE state = 'PENDING'
              AND attempts < ?
            ORDER BY created_at
            LIMIT 1
        """, (max_attempts,)).fetchone()

        if not row:
            return None

        updated = db.execute("""
            UPDATE actions
            SET state = 'EXECUTING',
                attempts = attempts + 1,
                claimed_at = ?,
                executor_id = ?
            WHERE id = ?
              AND state = 'PENDING'
        """, (
            now,
            EXECUTOR_ID,
            row["id"],
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
        SET state = 'PENDING',
            claimed_at = NULL,
            executor_id = NULL
        WHERE (
            state = 'EXECUTING'
            AND claimed_at < ?
        )
        OR (
            state = 'FAILED'
            AND attempts < ?
        )
    """, (
        now - timeout,
        max_attempts,
    ))
    db.commit()

def mark_failed(db, action_id: int, error: str, now: int | None = None):
    if now is None:
        now = int(time.time())

    db.execute("""
        UPDATE actions
        SET state = 'FAILED',
            last_error = ?,
            executed_at = ?
        WHERE id = ?
          AND state = 'EXECUTING'
    """, (
        error[:500],  # cap size defensively
        now,
        action_id,
    ))
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
