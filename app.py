import asyncio
from nio import AsyncClient, RoomMessageText

from env_config import (
    MATRIX_HOMESERVER,
    MATRIX_USER,
    MATRIX_ACCESS_TOKEN,
    SYNC_TIMEOUT,
)
from ingestion import handle_message


async def main():
    client = AsyncClient(MATRIX_HOMESERVER, MATRIX_USER)

    # Inject token (OTP / SSO compatible)
    client.access_token = MATRIX_ACCESS_TOKEN
    client.user_id = MATRIX_USER

    print("✅ Bot authenticated using access token")

    # 👉 CRITICAL: initial sync to obtain next_batch
    print("🔄 Performing initial sync...")
    await client.sync(timeout=SYNC_TIMEOUT)
    print("✅ Initial sync complete")

    # Register callback AFTER initial sync
    client.add_event_callback(
        lambda room, event: handle_message(client, room, event),
        RoomMessageText,
    )

    # Now this will work correctly
    await client.sync_forever(timeout=SYNC_TIMEOUT)


if __name__ == "__main__":
    asyncio.run(main())
