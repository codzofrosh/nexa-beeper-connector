# sidecar/main.py
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from sidecar.models import MessageEvent
from sidecar.worker import worker
from sidecar.metrics import Metrics
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("sidecar")

QUEUE_MAX = 1000
queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAX)
worker_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global worker_task
    log.info("🚀 AI Sidecar starting")

    worker_task = asyncio.create_task(worker(queue))

    try:
        yield
    finally:
        log.info("🛑 AI Sidecar shutting down")

        if worker_task:
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                log.info("🧠 AI worker stopped cleanly")


app = FastAPI(lifespan=lifespan)


@app.post("/message")
async def ingest(event: MessageEvent):
    try:
        queue.put_nowait(event)
    except asyncio.QueueFull:
        log.warning("🚨 Queue full, dropping message %s", event.message_id)
        raise HTTPException(status_code=429, detail="AI sidecar overloaded")

    return {"ok": True}

@app.get("/metrics")
async def metrics():
    return Metrics.snapshot(queue.qsize())