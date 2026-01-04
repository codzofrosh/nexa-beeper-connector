# sidecar/models.py
from pydantic import BaseModel
from typing import Literal, Optional

import time
class MessageEvent(BaseModel):
    platform: str
    room_id: str
    sender: str
    sender_name: str | None = None
    is_group: bool
    timestamp: int
    text: str
    message_id: str

class ActionResult(BaseModel):
    message_id: str
    platform: str
    room_id: str
    label: str
    action: Literal["NOTIFY", "ESCALATE", "SUPPRESS", "IGNORE"]
    confidence: float
    timestamp: int

class ActionEvent(BaseModel):
    message_id: str
    platform: str
    room_id: str
    label: str
    action: str
    confidence: float
    timestamp: int
