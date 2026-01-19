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
            # Step 3: idempotency guard
            if action["external_id"]:
                log.info(
                    "Action already executed, marking done",
                    extra={"action_id": action["id"]},
                )
                mark_done(db, action["id"], now)
                continue

            # Step 4: generate deterministic idempotency key
            external_id = make_external_id(action)

            # Step 5: persist idempotency key BEFORE side effect
            set_external_id(
                db,
                action_id=action["id"],
                external_id=external_id,
                now=now,
            )

            # Step 6: perform side-effect
            execute_action(action, external_id)

            # Step 7: mark success
            mark_done(db, action["id"], now)

        except Exception as e:
            log.exception(
                "💥 execution failed",
                extra={"action_id": action["id"]},
            )
            mark_failed(db, action["id"], now)
