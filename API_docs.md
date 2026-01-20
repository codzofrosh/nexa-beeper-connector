POST /message
    {
    "platform": "whatsapp",
    "room_id": "string",
    "sender": "string",
    "sender_name": "string",
    "is_group": false,
    "timestamp": 123,
    "text": "price please",
    "message_id": "unique-id"
    }
Guarantees:
    - idempotent by message_id + platform
    - always returns { "ok": true } or 429

GET /actions
[
  {
    "message_id": "msg-001",
    "platform": "whatsapp",
    "room_id": "r1",
    "label": "ENQUIRY",
    "action": "NOTIFY",
    "confidence": 0.85,
    "timestamp": 1767707539
  }
]

Supports:
/actions?since=<unix_ts>&limit=100


GET /metrics
{
  "processed": 123,
  "dropped": 2,
  "queue_depth": 0
}