"""Executor loop that polls the sidecar for EXECUTING actions.

The loop periodically fetches actions from the sidecar `/actions` API
and invokes `execute_action` on any action in the `EXECUTING` state.
"""

import time
import requests
import logging

from bridge.cursor.store import load_cursor, advance_cursor
from bridge.executor.actions import execute_action

log = logging.getLogger("bridge.executor")

SIDECAR_URL = "http://localhost:8080"


def execution_loop():
    """Continuously poll sidecar for actions and execute them."""
    log.info("🚀 Bridge execution loop started")

    while True:
        try:
            cursor = load_cursor()

            resp = requests.get(
                f"{SIDECAR_URL}/actions",
                params={"since": cursor},
                timeout=5,
            )
            resp.raise_for_status()

            actions = resp.json()
            for action in actions:
                if action.get("state") != "EXECUTING":
                    log.warning("Skipping non-executing action: %s", action.get("id"))
                    continue

                execute_action(action)   # ← YOUR domain logic
                advance_cursor(action["timestamp"])

        except Exception:
            log.exception("💥 Execution loop failure")

        time.sleep(2)
