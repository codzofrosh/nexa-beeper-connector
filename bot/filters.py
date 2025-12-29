def is_whatsapp_room(room) -> bool:
    """
    Heuristic detection for WhatsApp-backed Matrix rooms
    """
    if not room:
        return False

    name = (room.display_name or "").lower()
    topic = (room.topic or "").lower()

    # Strong signals
    if "whatsapp" in name or "whatsapp" in topic:
        return True

    # Phone number heuristic
    if any(char.isdigit() for char in name) and "+" in name:
        return True

    return False
