from nio import AsyncClient, RoomMessageText
from models import NormalizedEvent
from ai.classifier import classify
from ai.policy import decide
from actions import perform_action


async def handle_message(client, room, event):
    if not isinstance(event, RoomMessageText):
        return

    normalized = NormalizedEvent(
        event_id=event.event_id,
        room_id=room.room_id,
        sender_id=event.sender,
        timestamp=event.server_timestamp,
        text=event.body,
        is_group=room.is_group,
    )

    classification = classify(normalized.text)
    action = decide(normalized, classification)

    print("EVENT:", normalized)
    print("CLASS:", classification)
    print("ACTION:", action)
    print("-" * 40)

    await perform_action(client, action, normalized)
