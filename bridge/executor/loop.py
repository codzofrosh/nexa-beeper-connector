import time
import logging
from bridge.db.database import get_db
from bridge.executor.db import (
    claim_next_action,
    mark_done,
    mark_failed,
    recover_stuck_actions,
)
from bridge.executor.idempotency import make_external_id
from bridge.executor.actions import execute_action
from bridge.executor.db import set_external_id

log = logging.getLogger("bridge.executor.loop")

EXECUTOR_ID = "executor-1"  # later make this env-based

def executor_loop():
    db = get_db()
    log.info("🚀 Bridge execution loop started")

    while True:
        now = int(time.time())

        recover_stuck_actions(db, now)

        action = claim_next_action(db, now)
        if not action:
            time.sleep(1)
            continue

        try:
            external_id = action["external_id"]
            if not external_id:
                external_id = make_external_id(action)
                set_external_id(db, action["id"], external_id, now)

            execute_action(action, external_id)
            mark_done(db, action["id"], now)

        except Exception:
            log.exception("💥 execution failed", extra={"action_id": action["id"]})
            mark_failed(db, action["id"], now)

