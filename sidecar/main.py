# sidecar/main.py
import asyncio
import logging

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from sidecar.models import MessageEvent
from sidecar.worker import worker
from sidecar.metrics import Metrics
from sidecar.actions import fetch, fetch_since

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

# @app.get("/actions")
# async def get_actions(limit: int = 100):
#     return fetch(limit)

# @app.get("/actions")
# async def list_actions(
#     since: int = Query(0, description="Unix timestamp cursor"),
#     limit: int = Query(100, le=500),
# ):
#     actions = get_actions_since(since, limit)
#     return [a.dict() for a in actions]



@app.get("/actions")
def get_actions(since: int | None = None, limit: int = 100):
    if since is None:
        return fetch(limit)
    return fetch_since(since, limit)
