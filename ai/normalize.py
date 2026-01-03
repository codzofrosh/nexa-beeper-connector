def normalize_message(event):
    return {
        "platform": event.platform,
        "room_id": event.room_id,
        "sender": event.sender,
        "sender_name": event.sender_name,
        "is_group": event.is_group,
        "timestamp": event.timestamp,
        "text": (event.text or "").strip().lower(),
        "message_id": event.message_id,
    }
