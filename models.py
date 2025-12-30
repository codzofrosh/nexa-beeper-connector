from dataclasses import dataclass
from typing import Optional


@dataclass
class NormalizedEvent:
    event_id: str
    room_id: str
    sender_id: str
    timestamp: int
    text: str
    network: str = "unknown"
    is_group: bool = True


@dataclass
class ClassificationResult:
    intent: str
    sentiment: str
    confidence: float
