"""
Nexa Beeper Connector — Matrix listener entry point.

Starts an async Matrix client that:
  1. Authenticates with the Beeper homeserver using the access token in .env
  2. Performs an initial sync to get current room state
  3. Auto-accepts invites (bridge rooms are invite-only)
  4. Runs sync_forever() to continuously receive messages
  5. Forwards every incoming message to the ingestion pipeline

Run:
    python app.py
"""

import asyncio
import logging
from nio import (
    AsyncClient,
    InviteMemberEvent,
    RoomMessageText,
    SyncResponse,
)

from env_config import (
    MATRIX_HOMESERVER,
    MATRIX_USER,
    MATRIX_ACCESS_TOKEN,
    SYNC_TIMEOUT,
)
from ingestion import handle_message

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)


async def _on_invite(room, event: InviteMemberEvent, client: AsyncClient) -> None:
    """
    Auto-accept room invites.

    The mautrix bridge creates a new Matrix room for each WhatsApp conversation
    and invites the bot. Without auto-accept, those rooms are never joined and
    their messages are never received.
    """
    if event.state_key == client.user_id:
        log.info("Accepting invite to room %s", room.room_id)
        await client.join(room.room_id)


async def main() -> None:
    client = AsyncClient(MATRIX_HOMESERVER, MATRIX_USER)
    client.access_token = MATRIX_ACCESS_TOKEN
    client.user_id = MATRIX_USER

    log.info("Authenticated as %s on %s", MATRIX_USER, MATRIX_HOMESERVER)

    # Initial sync — obtains next_batch token so we don't replay old messages
    log.info("Performing initial sync...")
    resp = await client.sync(timeout=SYNC_TIMEOUT)
    if isinstance(resp, SyncResponse):
        log.info("Initial sync complete (next_batch: %s)", resp.next_batch[:16])
    else:
        log.warning("Initial sync returned unexpected response: %s — continuing anyway", resp)

    # Register callbacks AFTER initial sync so old events are not replayed
    client.add_event_callback(
        lambda room, event: handle_message(client, room, event),
        RoomMessageText,
    )
    client.add_event_callback(
        lambda room, event: _on_invite(room, event, client),
        InviteMemberEvent,
    )

    log.info("Listening for messages — press Ctrl+C to stop")

    # Reconnect loop: if sync_forever drops, wait briefly and restart
    retry_delay = 5  # seconds
    while True:
        try:
            await client.sync_forever(timeout=SYNC_TIMEOUT, full_state=True)
        except KeyboardInterrupt:
            log.info("Shutdown requested")
            break
        except Exception as exc:
            log.error("sync_forever raised %s — reconnecting in %ds", exc, retry_delay)
            await asyncio.sleep(retry_delay)
            # Back off gently (cap at 60s)
            retry_delay = min(retry_delay * 2, 60)
        else:
            # sync_forever returned normally (shouldn't happen) — exit cleanly
            break

    await client.close()
    log.info("Matrix client closed")


if __name__ == "__main__":
    asyncio.run(main())
