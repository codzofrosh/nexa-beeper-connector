# bridge/executor/actions.py
import logging
from .db import claim_next_action, mark_done, mark_failed
from time import sleep
log = logging.getLogger("bridge.executor.actions")


def execute_action(action: dict):
    """
    Execute a single AI-decided action.

    action schema (guaranteed by sidecar):
    {
        message_id: str
        platform: str
        room_id: str
        label: str
        action: str
        confidence: float
        timestamp: int
    }
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

