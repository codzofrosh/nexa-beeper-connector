from pydantic import BaseModel

class MessageEvent(BaseModel):
    platform: str
    room_id: str
    sender: str
    sender_name: str | None = None
    is_group: bool
    timestamp: int
    text: str
    message_id: str
