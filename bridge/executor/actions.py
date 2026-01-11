# bridge/executor/actions.py
"""Action execution helpers for the bridge executor.

This module exposes `execute_action` which applies the side-effect corresponding
to an AI-decided action, plus small helpers to avoid re-execution and to perform
side-effects in a single place.
"""

import logging
from time import sleep, time

log = logging.getLogger("bridge.executor.actions")


def already_executed(db, external_id: str) -> bool:
    """Return True if an action with `external_id` has already been marked DONE."""
    if not external_id:
        return False
    row = db.execute(
        "SELECT 1 FROM actions WHERE external_id = ? AND state = 'DONE' LIMIT 1",
        (external_id,),
    ).fetchone()
    return row is not None


def perform_side_effect(db, action: dict) -> str:
    """Perform the domain side-effect for `action` and return an external id.

    This is intentionally simple: it calls the internal handlers and then
    records a synthetic `external_id` in the DB for idempotency checks.
    """
    act = action["action"]

    if act == "NOTIFY":
        _handle_notify(action)
    elif act == "ESCALATE":
        _handle_escalate(action)
    elif act == "SUPPRESS":
        _handle_suppress(action)
    else:
        log.warning("Unknown action type: %s", act)

    # Simulate an external system id so replays can be detected.
    external_id = f"ext-{action.get('id')}-{int(time())}"

    try:
        db.execute(
            "UPDATE actions SET external_id = ? WHERE id = ?",
            (external_id, action.get("id")),
        )
        db.commit()
    except Exception:
        log.exception("failed to persist external_id for action %s", action.get("id"))

    return external_id


def execute_action(db, action):
    """Execute an action if it hasn't been executed already.

    Returns a status string: 'DONE' on success, 'SKIPPED' if already executed.
    """
    if already_executed(db, action.get("external_id")):
        log.info("Skipping already executed action %s", action.get("external_id"))
        return "SKIPPED"

    external_id = perform_side_effect(db, action)
    if external_id:
        # mark executed_at will be set by runner via mark_done; we just return DONE
        return "DONE"
    return "FAILED"


def _handle_notify(action):
    log.info(
        "🔔 NOTIFY | room=%s msg=%s",
        action["room_id"],
        action["message_id"],
    )
    # TODO: call Matrix API / WhatsApp bridge


def _handle_escalate(action):
    log.warning(
        "🚨 ESCALATE | room=%s msg=%s",
        action["room_id"],
        action["message_id"],
    )
    # TODO: alert human / ticket system


def _handle_suppress(action):
    log.info(
        "🙈 SUPPRESS | msg=%s",
        action["message_id"],
    )
    # intentionally do nothing
def execute_action(db, action):

    if already_executed(db, action["external_id"]):
        log.info("Skipping already executed action %s", action["external_id"])
        return "SKIPPED"
    perform_side_effect(action)
    return "DONE"

def _handle_notify(action):
    log.info(
        "🔔 NOTIFY | room=%s msg=%s",
        action["room_id"],
        action["message_id"],
    )
    # TODO: call Matrix API / WhatsApp bridge


def _handle_escalate(action):
    log.warning(
        "🚨 ESCALATE | room=%s msg=%s",
        action["room_id"],
        action["message_id"],
    )
    # TODO: alert human / ticket system


def _handle_suppress(action):
    log.info(
        "🙈 SUPPRESS | msg=%s",
        action["message_id"],
    )
    # intentionally do nothing

