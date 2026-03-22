import logging
from functools import lru_cache

from bridge.adapters.mautrix import MautrixConfig, MautrixSender

log = logging.getLogger("bridge.whatsapp")


@lru_cache(maxsize=1)
def _get_sender() -> MautrixSender:
    """Build the sender lazily so tests can patch env per-process."""
    return MautrixSender(MautrixConfig.from_env())

def send_whatsapp(*, room: str, text: str, idempotency_key: str) -> str:
    """
    Send into a mautrix-whatsapp bridged Matrix room.

    Must be:
    - idempotent
    - raise on failure
    - return external message id
    """
    event_id = _get_sender().send_text(
        room_id=room,
        text=text,
        txn_id=idempotency_key,
    )
    log.info("📤 WhatsApp SEND | room=%s | key=%s | event_id=%s", room, idempotency_key, event_id)
    return event_id
