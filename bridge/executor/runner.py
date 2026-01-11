from .db import claim_next_action, mark_done, mark_failed
from .actions import execute_action
from time import sleep, time
while True:
    action = claim_next_action(db, now=time.time())
    if not action:
        sleep(1)
        continue

    result = execute_action(db, action)
    if result == "DONE" or result == "SKIPPED":
        mark_done(db, action["id"], now)
    else:
        mark_failed(db, action["id"], now)