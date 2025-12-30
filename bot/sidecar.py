import asyncio
import logging
from fastapi import FastAPI
from pydantic import BaseModel
from ai.pipeline import run_pipeline

log = logging.getLogger("sidecar")
logging.basicConfig(level=logging.INFO)

app = FastAPI()
queue: asyncio.Queue = asyncio.Queue()


class Message(BaseModel):
    platform: str
    room_id: str
    sender: str
    sender_name: str | None = None
    is_group: bool
    timestamp: int
    text: str
    message_id: str


@app.post("/message")
async def ingest(msg: Message):
    await queue.put(msg)
    return {"ok": True}


async def worker():
    log.info("🧠 AI worker started")
    while True:
        msg = await queue.get()

        result = run_pipeline(msg.text)
        log.info(f"[AI] {result} :: {msg.text[:80]}")

        queue.task_done()


@app.on_event("startup")
async def startup():
    asyncio.create_task(worker())
    log.info("🚀 AI Sidecar ready")
