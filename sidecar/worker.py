# sidecar/worker.py
import asyncio
import logging
from sidecar.dedup import Deduplicator
from ai.pipeline import run_pipeline

log = logging.getLogger("sidecar.worker")

dedup = Deduplicator()

async def worker(queue: asyncio.Queue):
    log.info("🧠 AI worker started")

    while True:
        event = await queue.get()

        try:
            if dedup.seen_before(event.message_id):
                continue

            result = run_pipeline(event.text)

            log.info(
                "[AI] %s:%s :: %s",
                result["label"],
                result["action"],
                event.text[:80]
            )

        except Exception:
            log.exception("💥 Worker error while processing message")

        finally:
            queue.task_done()
