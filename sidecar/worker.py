# sidecar/worker.py
import asyncio
import logging
import time

from sidecar.dedup import Deduplicator
from sidecar.metrics import Metrics
from ai.pipeline import run_pipeline
from sidecar.actions import publish
from sidecar.models import ActionResult


log = logging.getLogger("sidecar.worker")

dedup = Deduplicator()


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
