def normalize_message(event, room):
    return {
        "room_id": room.room_id,
        "room_name": room.display_name,
        "sender": event.sender,
        "text": event.body,
        "timestamp": event.server_timestamp,
        "source": "whatsapp"
    }
