import logging
import uuid

log = logging.getLogger("bridge.whatsapp")

# in-memory idempotency store (TEMP – replace later)
_SENT = set()

def send_whatsapp(*, room: str, text: str, idempotency_key: str) -> str:
    """
    Simulate WhatsApp send.

    Must be:
    - idempotent
    - raise on failure
    - return external message id
    """

    if idempotency_key in _SENT:
        log.info("WhatsApp duplicate suppressed: %s", idempotency_key)
        return idempotency_key  # exactly-once illusion

    # simulate send
    #external_id = f"wa-{uuid.uuid4().hex[:8]}"
    log.info(
        "📤 WhatsApp SEND | room=%s | key=%s | text=%s",
        room,
        idempotency_key,
        text,
    )
    _SENT.add(idempotency_key)
    return idempotency_key


