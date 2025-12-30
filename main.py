# import asyncio
# import logging
# import os
# from dotenv import load_dotenv
# from nio import AsyncClient, RoomMessageText
# from bot.filters import is_whatsapp_room
# from ai.normalize import normalize_message
# from ai.pipeline import run_pipeline


# logging.basicConfig(level=logging.INFO)
# log = logging.getLogger("sidecar")
# logging.getLogger("nio.responses").setLevel(logging.ERROR)

# def load_config():
#     load_dotenv()

#     homeserver = os.getenv("MATRIX_HOMESERVER")
#     user_id = os.getenv("MATRIX_USER")
#     access_token = os.getenv("MATRIX_ACCESS_TOKEN")

#     missing = [k for k, v in {
#         "MATRIX_HOMESERVER": homeserver,
#         "MATRIX_USER": user_id,
#         "MATRIX_ACCESS_TOKEN": access_token,
#     }.items() if not v]

#     if missing:
#         raise RuntimeError(
#             f"Missing required env vars: {', '.join(missing)}"
#         )

#     return homeserver, user_id, access_token


# async def setup_client():
#     homeserver, user_id, token = load_config()

#     log.info("🔑 Initializing Matrix client from env")

#     client = AsyncClient(
#         homeserver=homeserver,
#         user=user_id,
#     )

#     # ✅ CORRECT for your matrix-nio version
#     client.restore_login(
#         user_id=user_id,
#         device_id="AI_SIDECAR",
#         access_token=token,
#     )

#     # Validate auth
#     await client.sync(timeout=3000)
#     log.info("✅ Authenticated successfully")

#     return client

# def on_message(room, event):
#     log.warning("🔥 EVENT RECEIVED: %s", type(event))
#     # 1️⃣ Ignore non-WhatsApp rooms
#     if not is_whatsapp_room(room):
#         return

#     # 2️⃣ Ignore non-text messages
#     if not isinstance(event, RoomMessageText):
#         return

#     # 3️⃣ Normalize (this is your contract)
#     msg = normalize_message(event, room)

#     # 4️⃣ Run AI pipeline
#     label = run_pipeline(msg)

#     # 5️⃣ Observe result (no side effects yet)
#     log.info(f"[AI] {label} :: {msg['text'][:80]}")

# async def main():
#     client = await setup_client()
#     rooms = client.rooms
#     log.info(f"📦 Joined rooms: {len(rooms)}")

#     for room_id, room in rooms.items():
#         log.info(f"ROOM: {room.display_name} | encrypted={room.encrypted}")

#     async def on_message(room, event):
#         room_name = getattr(room, "display_name", room.room_id)
#         log.info(f"💬 [{room_name}] {event.sender}: {event.body}")

#     client.add_event_callback(on_message, RoomMessageText)

#     log.info("🚀 AI Sidecar running (read-only)")
#     log.info("🔄 Performing initial full sync...")
#     import pdb; pdb.set_trace()
#     await client.sync(timeout=30000)
#     log.info(f"📦 Joined rooms after sync: {len(client.rooms)}")

#     try:
#         await client.sync_forever(timeout=30000)
#     finally:
#         await client.close()

# if __name__ == "__main__":
#     asyncio.run(main())
import uvicorn
from config.settings import AI_SIDECAR_HOST, AI_SIDECAR_PORT

if __name__ == "__main__":
    uvicorn.run(
        "bot.sidecar:app",
        host=AI_SIDECAR_HOST,
        port=AI_SIDECAR_PORT,
        reload=False,
    )
