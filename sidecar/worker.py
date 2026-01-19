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
from sidecar.actions_store import persist_action

log = logging.getLogger("sidecar.worker")

dedup = Deduplicator()


def persist_action_db(db, action: ActionResult):
    """Persist an ActionResult using a DB connection.

    Low-level helper that mirrors the older insert style. Kept separate from
    the `sidecar.actions.store.persist_action` helper which accepts a dict
    and handles connection management.
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
            if dedup.seen_before(event.message_id):
                log.debug(
                    "Duplicate message skipped",
                    extra={"message_id": event.message_id},
                )
                continue

            result = run_pipeline(event.text)

            inserted = persist_action({
                "message_id": event.message_id,
                "platform": event.platform,
                "room_id": event.room_id,
                "label": result["label"],
                "action": result["action"],
                "confidence": result["confidence"],
            })

            if not inserted:
                log.info(
                    "Duplicate action ignored by DB",
                    extra={"message_id": event.message_id},
                )

        except Exception:
            Metrics.dropped += 1
            log.exception(
                "💥 Worker error while processing message",
                extra={"message_id": getattr(event, "message_id", None)},
            )

        finally:
            queue.task_done()
