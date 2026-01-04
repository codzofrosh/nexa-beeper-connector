from typing import List
from threading import Lock
from sidecar.models import ActionEvent

_ACTIONS: List[ActionEvent] = []
_LOCK = Lock()

def add_action(action: ActionEvent) -> None:
    with _LOCK:
        _ACTIONS.append(action)

def get_actions_since(since: int, limit: int = 100) -> List[ActionEvent]:
    with _LOCK:
        results = [a for a in _ACTIONS if a.timestamp > since]
        return results[:limit]
