import hashlib

def make_external_id(action: dict) -> str:
    """
    Deterministic idempotency key.
    Same action → same external id forever.
    """
    raw = f"{action['platform']}:{action['room_id']}:{action['message_id']}:{action['action']}"
    return hashlib.sha256(raw.encode()).hexdigest()
