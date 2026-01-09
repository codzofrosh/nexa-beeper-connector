"""AI worker: consume messages from the queue and emit actions.

This worker loops on an asyncio.Queue populated by the HTTP API and
runs the AI pipeline. Results are persisted and published (idempotent
insert) so the executor can later claim and execute actions.
"""

import asyncio
import logging
import time
import sqlite3

from sidecar.dedup import Deduplicator
from sidecar.metrics import Metrics
from ai.pipeline import run_pipeline
from sidecar.actions import publish
from sidecar.models import ActionResult
from sidecar.db import get_conn


log = logging.getLogger("sidecar.worker")

dedup = Deduplicator()


def persist_action(db, action: ActionResult):
    """Persist an incoming action as PENDING (best-effort across schemas).

    Attempts to insert with a 'state'/'created_at' schema first and falls
    back to the existing timestamp-only schema if necessary so this works
    on existing databases without migrations.
    """
    try:
        db.execute("""
            INSERT OR IGNORE INTO actions (
                message_id, platform, room_id,
                label, action, confidence,
                state, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'PENDING', ?)
        """, (
            action.message_id,
            action.platform,
            action.room_id,
            action.label,
            action.action,
            action.confidence,
            action.timestamp,
        ))
        db.commit()
    except sqlite3.OperationalError:
        # Fallback for older schema (no state/created_at columns)
        db.execute("""
            INSERT OR IGNORE INTO actions (
                message_id, platform, room_id,
                label, action, confidence, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            action.message_id,
            action.platform,
            action.room_id,
            action.label,
            action.action,
            action.confidence,
            action.timestamp,
        ))
        db.commit()


async def worker(queue: asyncio.Queue):
    log.info("🧠 AI worker started")

    while True:
        event = await queue.get()

        try:
            # Dedup check (must still mark task done)
            if dedup.seen_before(event.message_id):
                log.debug(
                    "Duplicate message skipped",
                    extra={"message_id": event.message_id},
                )
                continue

            result = run_pipeline(event.text)

            # Defensive check (future-proofing)
            if not isinstance(result, dict):
                raise ValueError("run_pipeline must return dict")

            label = result.get("label")
            action = result.get("action")

            action_result = ActionResult(
                message_id=event.message_id,
                platform=event.platform,
                room_id=event.room_id,
                label=label,
                action=action,
                confidence=result.get("confidence", 1.0),
                timestamp=int(time.time())
            )

            # Persist as PENDING (best-effort). This replaces earlier
            # in-memory list behavior so actions survive restarts.
            conn = get_conn()
            try:
                persist_action(conn, action_result)
            finally:
                conn.close()

            inserted = publish(action_result)

            if inserted:
                Metrics.processed += 1
                log.info("[AI] %s:%s :: %s",
                    action_result.label,
                    action_result.action,
                    event.text[:80],
                )
            else:
                log.info("duplicate action ignored: %s", action_result.message_id)

        except Exception:
            Metrics.dropped += 1
            log.exception(
                "💥 Worker error while processing message",
                extra={"message_id": getattr(event, "message_id", None)},
            )

        finally:
            queue.task_done()
