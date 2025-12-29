import logging
from nio import MatrixRoom, RoomMessageText

from ai.classifier import classify
from ai.policy import decide

log = logging.getLogger("ai-sidecar")


async def on_message(room: MatrixRoom, event: RoomMessageText, client):
    text = event.body
    sender = event.sender

    log.info(f"[{room.room_id}] {sender}: {text[:100]}")

    classification = classify(text)
    action = decide(classification)

    log.info(f"→ classification={classification}, action={action}")

    if action == "NOTIFY":
        await client.room_send(
            room.room_id,
            "m.reaction",
            {
                "m.relates_to": {
                    "rel_type": "m.annotation",
                    "event_id": event.event_id,
                    "key": "🔔",
                }
            },
        )
