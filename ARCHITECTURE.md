# Unified Architecture - Merge Strategy

## Overview
The codebase has been refactored to merge two parallel functionalities into a single unified pipeline:
1. **Message Classification (LLM-based)** → Now in `message_service.py`
2. **Database Persistence & Idempotency** → Now in `database.py`

Both are orchestrated together in `main.py` through the unified `UnifiedMessageService`.

## Architecture

### Service Layer Pattern

```
API Request
    ↓
UnifiedMessageService.process_message()
    ├── 1. MessageClassificationService.classify()
    │   ├── Try Ollama (local)
    │   ├── Fall back to HuggingFace (cloud)
    │   └── Fall back to Rule-based (always works)
    │
    ├── 2. ActionDecisionService.decide_action()
    │   └── Decide action based on priority + user status
    │
    ├── 3. DatabaseService.store_message()
    │   └── Persist message with classification (deduped)
    │
    ├── 4. DatabaseService.store_action()
    │   └── Persist action decision (deduped)
    │
    └── Return unified result
        ↓
API Response
```

## Key Components

### 1. `database.py` - DatabaseService
**Responsibility**: All database operations with thread-safety and deduplication

**Features**:
- `store_message()` - Insert messages with deduplication via PRIMARY KEY
- `store_action()` - Insert actions with deduplication via UNIQUE constraint
- `get_message()` / `get_action()` - Retrieve stored data
- `get_pending_actions()` - Get actions ready for execution
- `update_action_status()` - Mark actions as completed
- `get_statistics()` - Aggregate metrics
- `get_user_status()` / `update_user_status()` - Manage user state
- `cleanup_old_cache()` - TTL-based cache cleanup

**Database Schema**:
```sql
CREATE TABLE messages (
    id TEXT PRIMARY KEY,           -- Deduplication key
    platform, sender, room_id, content, timestamp,
    classification TEXT,           -- JSON of classification result
    classifier_used TEXT,          -- Which classifier was used
    confidence REAL,               -- Classification confidence
    created_at, updated_at
)

CREATE TABLE actions (
    id INTEGER PRIMARY KEY,
    message_id TEXT UNIQUE,        -- Deduplication: one action per message
    action_type TEXT,              -- notify, escalate, suppress, etc.
    priority TEXT,                 -- urgent, high, normal, low
    status TEXT,                   -- PENDING, COMPLETED, FAILED, etc.
    action_data TEXT,              -- JSON metadata
    classification_data TEXT,      -- Full classification details
    created_at, executed_at, last_error
)

CREATE TABLE user_status (
    user_id TEXT PRIMARY KEY,
    status TEXT,                   -- available, busy, dnd
    auto_reply_message TEXT,
    updated_at
)

CREATE TABLE message_cache (
    message_id TEXT PRIMARY KEY,
    platform, sender, timestamp,
    cached_at
)
```

### 2. `message_service.py` - Classification & Decision Services

#### MessageClassificationService
**Responsibility**: Classify messages using multiple backends with graceful fallback

**Methods**:
- `classify(message: str) → Dict` - Main entry point
  - Tries Ollama first (local, fast)
  - Falls back to HuggingFace (cloud, if API key available)
  - Falls back to rule-based (always works)
  
- `_classify_with_ollama()` - Local LLM classification
- `_classify_with_huggingface()` - Cloud API classification
- `_classify_rule_based()` - Rule-based fallback

**Returns**:
```python
{
    "priority": "urgent|high|normal|low",
    "category": "work|personal|social|marketing",
    "confidence": 0.0-1.0,
    "reasoning": "explanation of decision",
    "requires_action": bool,
    "classifier_used": "ollama|huggingface|rule-based"
}
```

#### ActionDecisionService
**Responsibility**: Decide what action to take based on classification + user status

**Method**: `decide_action(priority: str, user_status: str) → str`

**Decision Matrix**:
```
User Status: AVAILABLE
  - Any priority → "none" (user sees normally)

User Status: BUSY
  - urgent/high → "remind" (notify later)
  - normal/low → "none" (just store)

User Status: DND (Do Not Disturb)
  - urgent → "notify" (break through DND)
  - high/normal/low → "auto_reply" (send auto-response)
```

#### UnifiedMessageService
**Responsibility**: Orchestrate the complete message processing pipeline

**Method**: `process_message(...) → Dict`

**Processing Steps**:
1. Classify message
2. Decide action based on user status
3. Store message (with deduplication)
4. Store action (with deduplication)
5. Return unified result

**Return Values**:
- `status: "success"` - Normal processing
- `status: "duplicate"` - Message was already processed
- `status: "error"` - Something went wrong

### 3. `main.py` - API Layer

**Changes**:
- Removed all inline classification logic
- Removed all inline database operations
- Uses service layer exclusively
- Cleaner, more testable endpoints

**Services Initialization**:
```python
db_service = DatabaseService(db_path=DB_PATH)
classifier_service = MessageClassificationService(...)
message_service = UnifiedMessageService(db_service, classifier_service)
```

**Updated Endpoints**:
```
POST /api/messages/classify
  → Uses UnifiedMessageService.process_message()
  → Single call handles classification + persistence

POST /api/user/status
  → Uses DatabaseService.update_user_status()

GET /api/user/status
  → Uses DatabaseService.get_user_status()

GET /api/actions/pending
  → Uses DatabaseService.get_pending_actions()

GET /api/messages/recent
  → Uses DatabaseService.get_recent_messages()

GET /api/stats
  → Uses DatabaseService.get_statistics()

GET /health
  → No changes
```

## Benefits of Unified Architecture

### 1. **Single Responsibility**
- Each service handles one concern
- Easy to test, modify, or replace

### 2. **Deduplication Built-in**
- Database constraints prevent duplicate messages/actions
- Message cache table for TTL-based cleanup
- No duplicate processing

### 3. **Guaranteed Consistency**
- Classification → Decision → Persistence all atomic
- No orphaned messages without actions
- No actions without messages

### 4. **Easier Testing**
- Mock services independently
- Test classification without DB
- Test DB operations without LLM

### 5. **Better Error Handling**
- Unified error reporting
- Graceful fallbacks built-in
- Clear error messages

### 6. **Cleaner API**
- Single endpoint handles complete flow
- Reduced client complexity
- Better response structure

## Migration from Old Code

### Old Flow (Parallel)
```
API → Classify → Store Classification
API → Store Message → Store Action
```

### New Flow (Unified)
```
API → UnifiedMessageService
       ├─ Classify
       ├─ Decide
       ├─ Store Message (deduped)
       ├─ Store Action (deduped)
       └─ Return Result
```

## File Structure

```
sidecar/
├── database.py          [NEW] DatabaseService - all DB operations
├── message_service.py   [NEW] Classification + Decision + Orchestration
├── main.py              [REFACTORED] API layer using services
├── models.py            [UNCHANGED] Pydantic models
├── dedup.py             [DEPRECATED] Functionality moved to database.py
├── db.py                [DEPRECATED] Functionality moved to database.py
└── ... other files
```

## Usage Example

### Before (Old Parallel Approach)
```python
# Step 1: Classify somewhere
classification = classify_message(content)

# Step 2: Store separately
store_message(message_id, classification)
store_action(message_id, action_type)
```

### After (New Unified Approach)
```python
# Single call does everything
result = message_service.process_message(
    message_id=message_id,
    platform=platform,
    sender=sender,
    content=content,
    timestamp=timestamp,
    user_id=user_id
)

# Result contains everything
print(result["classification"])  # Full classification
print(result["action_type"])     # Decided action
print(result["action_id"])       # Stored action ID
```

## Testing Strategy

### Unit Tests
```python
# Test classification independently
service = MessageClassificationService()
result = service.classify("test message")
assert result["priority"] in ["urgent", "high", "normal", "low"]

# Test decision logic independently
action = ActionDecisionService.decide_action("urgent", "dnd")
assert action == "notify"

# Test database independently
db = DatabaseService()
stored = db.store_message("msg1", "platform", "sender", "content", 123)
assert stored == True
```

### Integration Tests
```python
# Test complete pipeline
unified = UnifiedMessageService(db_service, classifier_service)
result = unified.process_message(...)
assert result["status"] == "success"
assert result["action_id"] is not None

# Test deduplication
result2 = unified.process_message(...)  # Same message
assert result2["status"] == "duplicate"
```

## Configuration

Environment variables (unchanged):
```bash
OLLAMA_URL=http://localhost:11435
OLLAMA_MODEL=llama3.2:1b
USE_OLLAMA=true
HF_API_KEY=your_api_key
DB_PATH=data/nexa.db
```

## Performance Considerations

### Thread Safety
- All database operations protected by locks
- Safe for concurrent requests
- SQLite with check_same_thread=False

### Deduplication
- Message IDs as PRIMARY KEY → O(1) duplicate detection
- Action message_id as UNIQUE → O(1) duplicate detection
- No database scans needed

### Fallback Strategy
- Ollama tries first (local, <100ms)
- HuggingFace tries next (cloud, 1-2s)
- Rule-based always works (<1ms)
- Automatic retry logic built-in

## Future Improvements

1. **Async Database Operations**
   - Currently synchronous with locks
   - Could use async SQLite driver

2. **Batch Processing**
   - Process multiple messages at once
   - Reduce database round-trips

3. **Distributed Caching**
   - Redis for message deduplication
   - Shared cache across instances

4. **Audit Logging**
   - Track all classification decisions
   - Enable debugging and monitoring

5. **Custom Classifiers**
   - Add more classification backends
   - Support for specialized models
