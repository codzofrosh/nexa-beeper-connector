# Quick Reference: Unified Message Service

## TL;DR

The codebase now has a clean three-layer architecture:

```
┌─────────────────────────────────┐
│  API Layer (main.py)            │  FastAPI endpoints
├─────────────────────────────────┤
│  Service Layer                  │  
│  ├─ UnifiedMessageService       │  Orchestrates everything
│  ├─ MessageClassificationService│  Classifies messages
│  └─ ActionDecisionService       │  Decides what to do
├─────────────────────────────────┤
│  Data Layer (database.py)       │  DatabaseService
└─────────────────────────────────┘
```

## Starting the Service

```bash
# Terminal 1: Start sidecar
python sidecar/main.py

# Terminal 2: Test with interactive demo
python tests/interactive_demo.py
```

## Using the Message Service Programmatically

### Complete Pipeline
```python
from sidecar.database import DatabaseService
from sidecar.message_service import (
    MessageClassificationService,
    UnifiedMessageService
)

# Initialize
db = DatabaseService()
classifier = MessageClassificationService()
service = UnifiedMessageService(db, classifier)

# Process message
result = service.process_message(
    message_id="msg_123",
    platform="matrix",
    sender="user@example.com",
    content="URGENT: Server down!",
    timestamp=1234567890,
    user_id="default_user"
)

# Check result
print(result["status"])           # "success" or "duplicate" or "error"
print(result["priority"])          # "urgent", "high", "normal", "low"
print(result["action_type"])       # "notify", "remind", "auto_reply", "none"
print(result["classification"])    # Full classification dict
```

### Classification Only
```python
from sidecar.message_service import MessageClassificationService

clf = MessageClassificationService()
result = clf.classify("URGENT: Something broke!")

print(result["priority"])          # "urgent"
print(result["confidence"])        # 0.85
print(result["classifier_used"])   # "ollama" or "huggingface" or "rule-based"
```

### Database Only
```python
from sidecar.database import DatabaseService

db = DatabaseService()

# Store a message
db.store_message(
    message_id="msg_123",
    platform="matrix",
    sender="user@example.com",
    content="Hello world",
    timestamp=1234567890,
    classification={"priority": "normal", ...}
)

# Store an action
action_id = db.store_action(
    message_id="msg_123",
    action_type="notify",
    priority="normal"
)

# Retrieve
message = db.get_message("msg_123")
action = db.get_action("msg_123")

# Get statistics
stats = db.get_statistics()
print(stats["total_messages"])
print(stats["pending_actions"])
```

### User Status Management
```python
from sidecar.database import DatabaseService

db = DatabaseService()

# Set user status
db.update_user_status(
    user_id="user@example.com",
    status="dnd",
    auto_reply="I'm currently unavailable"
)

# Get user status
status = db.get_user_status("user@example.com")
print(status["status"])      # "available", "busy", or "dnd"
print(status["auto_reply"])  # Auto-reply message
```

## API Endpoints

### POST /api/messages/classify
**Request**:
```json
{
  "id": "unique_msg_id",
  "platform": "matrix",
  "sender": "@user:example.com",
  "content": "URGENT: Help!",
  "timestamp": 1234567890,
  "room_id": "optional_room",
  "metadata": {}
}
```

**Response**:
```json
{
  "message_id": "unique_msg_id",
  "action_id": 1,
  "action_type": "notify",
  "priority": "urgent",
  "classification": {
    "priority": "urgent",
    "category": "work",
    "confidence": 0.85,
    "reasoning": "Multiple urgent indicators",
    "requires_action": true,
    "classifier_used": "ollama"
  },
  "status": "pending",
  "user_status": "available"
}
```

### POST /api/user/status
**Request**:
```json
{
  "user_id": "default_user",
  "status": "dnd",
  "auto_reply_message": "I'm unavailable"
}
```

### GET /api/user/status?user_id=default_user
**Response**:
```json
{
  "user_id": "default_user",
  "status": "available",
  "auto_reply_message": null
}
```

### GET /api/actions/pending?limit=50
**Response**:
```json
{
  "actions": [...],
  "count": 10
}
```

### GET /api/messages/recent?limit=20
**Response**:
```json
{
  "messages": [...],
  "count": 20
}
```

### GET /api/stats
**Response**:
```json
{
  "total_messages": 150,
  "pending_actions": 5,
  "priority_breakdown": {
    "urgent": 2,
    "high": 8,
    "normal": 120,
    "low": 20
  },
  "classifier_breakdown": {
    "ollama": 140,
    "rule-based": 10
  },
  "ollama_enabled": true,
  "ollama_model": "llama3.2:1b",
  "classifier": "ollama"
}
```

### GET /health
**Response**:
```json
{
  "status": "ok",
  "service": "nexa-sidecar",
  "ollama_available": true,
  "ollama_model": "llama3.2:1b",
  "hf_available": false,
  "db_path": "data/nexa.db"
}
```

## Configuration

```bash
# Database
DB_PATH=data/nexa.db

# Ollama (local LLM)
OLLAMA_URL=http://localhost:11435
OLLAMA_MODEL=llama3.2:1b
USE_OLLAMA=true

# HuggingFace (cloud LLM)
HF_API_KEY=your_api_key_here
HF_MODEL=mistralai/Mistral-7B-Instruct-v0.2
```

## Classification Priority Rules

### Rule-Based Fallback
```
URGENT:
  - Contains "urgent", "asap", "emergency", "critical", "help", "down"
  - Contains 2+ urgent keywords
  - Contains 3+ exclamation marks (!!!)
  - Confidence: 0.75-0.85

HIGH:
  - Contains "important", "deadline", "meeting", "client", "soon"
  - Confidence: 0.70

NORMAL:
  - Contains "?"
  - Confidence: 0.65

LOW:
  - Everything else
  - Confidence: 0.60
```

### Action Decision Matrix

```
                AVAILABLE       BUSY            DND
URGENT          none            remind          notify
HIGH            none            remind          auto_reply
NORMAL          none            none            auto_reply
LOW             none            none            auto_reply
```

## Error Handling

All operations return clear status codes:

```python
# Success
{"status": "success", "action_id": 1, ...}

# Duplicate (safely ignored)
{"status": "duplicate", "message_id": "...", ...}

# Error
{"status": "error", "error": "Error message", ...}
```

## Testing

### Quick Test
```bash
# Run demo
python tests/test_demo.py

# Interactive testing
python tests/interactive_demo.py
```

### Unit Tests
```python
# Test classifier independently
from sidecar.message_service import MessageClassificationService
clf = MessageClassificationService()
result = clf.classify("test")
assert result["priority"] in ["urgent", "high", "normal", "low"]

# Test database independently
from sidecar.database import DatabaseService
db = DatabaseService()
success = db.store_message(...)
assert success == True

# Test decision logic
from sidecar.message_service import ActionDecisionService
action = ActionDecisionService.decide_action("urgent", "dnd")
assert action == "notify"
```

## Troubleshooting

### Q: Service won't start
**A**: Check if port 8000 is available
```bash
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows
```

### Q: Ollama not connecting
**A**: Make sure Ollama is running and listening
```bash
curl http://localhost:11435/api/tags
```

### Q: Database locked
**A**: Another instance has the database open. Close or restart.

### Q: Classification taking too long
**A**: Likely waiting for Ollama. Check `classifier_used` in response:
- "ollama": Using local LLM (1-5s)
- "huggingface": Using cloud API (2-10s)
- "rule-based": Using rules (<1ms)

## Common Patterns

### Process and track a message
```python
service = UnifiedMessageService(db, classifier)

# Process
result = service.process_message(...)

if result["status"] == "success":
    action_id = result["action_id"]
    # Later: update action status
    db.update_action_status(action_id, "COMPLETED")
elif result["status"] == "duplicate":
    print("Already processed")
else:
    print(f"Error: {result['error']}")
```

### Get pending work
```python
db = DatabaseService()
pending = db.get_pending_actions(limit=10)

for action in pending:
    print(f"Action {action['id']}: {action['action_type']}")
    
    # Execute action...
    
    # Mark complete
    db.update_action_status(action['id'], "COMPLETED")
```

### Check user status
```python
db = DatabaseService()
status = db.get_user_status("user@example.com")

if status["status"] == "dnd":
    print(f"User is away: {status['auto_reply']}")
elif status["status"] == "busy":
    print("User is busy, remind later")
else:
    print("User is available")
```

## Files Overview

| File | Purpose |
|------|---------|
| `sidecar/main.py` | FastAPI application and endpoints |
| `sidecar/database.py` | Database service with thread-safety |
| `sidecar/message_service.py` | Classification, decision, orchestration |
| `tests/test_demo.py` | Automated demo script |
| `tests/interactive_demo.py` | Interactive testing tool |
| `ARCHITECTURE.md` | Detailed architectural documentation |
| `MERGE_SUMMARY.md` | Summary of changes |

## Next Steps

1. Run tests to verify everything works
2. Check the ARCHITECTURE.md for detailed design
3. Read MERGE_SUMMARY.md for what changed
4. Deploy with confidence!
