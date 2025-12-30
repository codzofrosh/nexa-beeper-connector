from nio import AsyncClient


async def react(
    client: AsyncClient,
    room_id: str,
    event_id: str,
    emoji: str,
):
    await client.room_send(
        room_id=room_id,
        message_type="m.reaction",
        content={
            "m.relates_to": {
                "rel_type": "m.annotation",
                "event_id": event_id,
                "key": emoji,
            }
        },
    )


async def perform_action(client, action, event):
    if action == "NOTIFY":
        await react(client, event.room_id, event.event_id, "🔔")

    elif action == "ESCALATE":
        await react(client, event.room_id, event.event_id, "🚨")

    elif action == "SUPPRESS":
        await react(client, event.room_id, event.event_id, "🙈")

    # IGNORE → do nothing
