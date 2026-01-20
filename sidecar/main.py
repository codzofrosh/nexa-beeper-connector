"""AI Sidecar HTTP server.

Exposes endpoints to ingest messages into the AI pipeline and to inspect
persisted actions and metrics. The worker runs asynchronously and an
executor loop (bridge) is started in a short-lived thread.
"""

import asyncio
import logging
import threading
import os

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from sidecar.models import MessageEvent
from sidecar.worker import worker
from sidecar.metrics import Metrics
from sidecar.actions import fetch, fetch_since
from bridge.cursor.store import init_cursor
from bridge.executor.loop import executor_loop
from bridge.db.database import init_db
from bridge.db.database import get_db
from sidecar.migrations import migrate

init_db()
db = get_db()
migrate(db)
init_cursor()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("sidecar")

QUEUE_MAX = 1000
queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAX)
worker_task: asyncio.Task | None = None

# threading.Thread(
#     target=execution_loop,
#     daemon=True,
#     name="ai-executor",
# ).start()

@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv("ENABLE_EXECUTOR") == "1":
        log.info("⚙️ Executor ENABLED")
        threading.Thread(
            target=executor_loop,
            daemon=True,
            name="ai-executor",
        ).start()
    else:
        log.info("🛑 Executor DISABLED (decision-only mode)")

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
    """Enqueue an inbound `MessageEvent` for AI processing.

    The API returns 429 if the internal queue is full to provide backpressure.
    """
    try:
        queue.put_nowait(event)
    except asyncio.QueueFull:
        log.warning("🚨 Queue full, dropping message %s", event.message_id)
        raise HTTPException(status_code=429, detail="AI sidecar overloaded")

    return {"ok": True}

@app.get("/metrics")
async def metrics():
    """Return a JSON snapshot of runtime metrics for the sidecar.

    Useful for local debugging and automated health checks.
    """
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


