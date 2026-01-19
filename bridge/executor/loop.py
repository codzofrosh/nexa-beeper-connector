import time
import logging

from bridge.db.database import get_db
from bridge.executor.db import (
    claim_next_action,
    mark_done,
    mark_failed,
    recover_stuck_actions,
    set_external_id,
)
from bridge.executor.actions import execute_action
from bridge.executor.idempotency import make_external_id

log = logging.getLogger("bridge.executor")


def executor_loop():
    db = get_db()
    log.info("🚀 Bridge execution loop started")

    while True:
        now = int(time.time())

        # Step 1: recover abandoned executions
        recover_stuck_actions(db, now)

        # Step 2: atomically claim next action
        action = claim_next_action(db, now)
        if not action:
            time.sleep(1)
            continue

        try:
            external_id = action["external_id"] or make_external_id(action)

            if not action["external_id"]:
                set_external_id(db, action["id"], external_id, now)

            execute_action(action, external_id)
            mark_done(db, action["id"], now)

        except Exception as e:
            log.exception("Execution failed", extra={"action_id": action["id"]})
            mark_failed(db, action["id"], str(e), now)