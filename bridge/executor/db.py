"""DB helpers used by the bridge executor.

These helpers implement claiming/locking semantics for actions so multiple
executors can run concurrently and avoid races.
"""

from typing import Optional
import time
from bridge.executor.identity import EXECUTOR_ID


def claim_next_action(db, now: int) -> Optional[dict]:
    """Attempt to atomically claim the next pending action.

    Returns the claimed action row or None if none available or claim lost.
    """
    with db:
        row = db.execute("""
            SELECT id FROM actions
            WHERE state IN ('PENDING', 'EXECUTING') AND external_id IS NULL
            ORDER BY created_at
            LIMIT 1
        """).fetchone()

        if not row:
            return None

        updated = db.execute("""
            UPDATE actions
            SET state = 'EXECUTING',
                claimed_at = ?,
                executor_id = ?
            WHERE id = ?
              AND state = 'PENDING'
        """, (now, EXECUTOR_ID, row["id"]))

        if updated.rowcount != 1:
            return None  # lost race safely

        return db.execute(
            "SELECT * FROM actions WHERE id = ?", (row["id"],)
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


def recover_stuck_actions(db, now: int, timeout: int = 60):
    """Reset long-running executing actions back to PENDING for retry."""
    db.execute("""
        UPDATE actions
        SET state = 'PENDING',
            claimed_at = NULL,
            executor_id = NULL
        WHERE state = 'EXECUTING'
          AND claimed_at < ?
    """, (now - timeout,))
    db.commit()


def mark_failed(db, action_id: int, now: int = None):
    """Mark an executing action as failed."""
    if now is None:
        now = int(time.time())
    db.execute("""
        UPDATE actions
        SET state = 'FAILED',
            executed_at = ?
        WHERE id = ?
          AND state = 'EXECUTING'
    """, (now, action_id))
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
