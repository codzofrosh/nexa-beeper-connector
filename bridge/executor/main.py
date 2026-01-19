import logging
import threading
from fastapi import FastAPI
from bridge.db.database import init_db
from bridge.db.database import get_db
from sidecar.migrations import migrate
from bridge.executor.loop import executor_loop
from bridge.cursor.store import init_cursor
log = logging.getLogger("bridge.executor")

app = FastAPI()
init_db()
db = get_db()
migrate(db)
init_cursor()

@app.on_event("startup")
def start_executor():
    log.info("🚀 Bridge executor starting")
    t = threading.Thread(target=executor_loop, daemon=True)
    t.start()

@app.on_event("shutdown")
def stop_executor():
    log.info("🛑 Bridge executor stopping")
