from time import sleep, time
import logging

from bridge.executor.db import (
    get_db,
    claim_next_action,
    mark_done,
    mark_failed,
)
from bridge.executor.actions import execute_action
from bridge.executor.idempotency import make_external_id
from bridge.executor.db import set_external_id
log = logging.getLogger("bridge.executor")

db = get_db()

while True:
    now = int(time())

    action = claim_next_action(db, now)
    if not action:
        sleep(1)
        continue

    try:
        # If external_id exists, side-effect was already attempted
        if action["external_id"]:
            log.info(
                "Action already has external_id, marking done",
                extra={"action_id": action["id"]},
            )
            mark_done(db, action["id"], now)
            continue

        external_id = make_external_id(action)

        set_external_id(
            db,
            action_id=action["id"],
            external_id=external_id,
            now=now,
        )

        execute_action(action, external_id)

        mark_done(db, action["id"], now)

    except Exception:
        log.exception(
            "Executor failed while processing action",
            extra={"action_id": action["id"]},
        )
        mark_failed(db, action["id"], now)
