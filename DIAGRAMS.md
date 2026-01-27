# Architecture Diagrams

## System Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                     CLIENT APPLICATIONS                         │
│                  (Matrix, WhatsApp, Tests)                      │
└────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP
                              ▼
┌────────────────────────────────────────────────────────────────┐
│                    FASTAPI APPLICATION                          │
│                         (main.py)                               │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ GET /health                POST /api/messages/classify   │   │
│  │ GET /api/user/status      POST /api/user/status         │   │
│  │ GET /api/actions/pending  GET /api/messages/recent      │   │
│  │ GET /api/stats                                          │   │
│  └─────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────┘
                              │
                              │ Uses Services
                              ▼
┌────────────────────────────────────────────────────────────────┐
│                    SERVICE LAYER                                │
│                                                                  │
│  ┌──────────────────────┐  ┌──────────────────────┐            │
│  │ UnifiedMessage       │  │ DatabaseService      │            │
│  │ Service              │  │                      │            │
│  │                      │  │ • store_message()    │            │
│  │ • process_message()  │  │ • store_action()     │            │
│  │   ├─ Classify        │  │ • get_message()      │            │
│  │   ├─ Decide          │  │ • get_statistics()   │            │
│  │   ├─ Store           │  │ • update_status()    │            │
│  │   └─ Return Result   │  │                      │            │
│  └──────────────────────┘  └──────────────────────┘            │
│                                                                  │
│  ┌──────────────────────────────────────────────────────┐      │
│  │ MessageClassificationService                         │      │
│  │                                                      │      │
│  │ classify(message)                                   │      │
│  │   ├─ Try: Ollama (local LLM)                        │      │
│  │   │   └─ POST /api/generate                         │      │
│  │   ├─ Try: HuggingFace (cloud API)                   │      │
│  │   │   └─ POST api-inference.huggingface.co          │      │
│  │   └─ Fallback: Rule-based                           │      │
│  │       └─ Keyword matching                           │      │
│  └──────────────────────────────────────────────────────┘      │
│                                                                  │
│  ┌──────────────────────────────────────────────────────┐      │
│  │ ActionDecisionService                                │      │
│  │                                                      │      │
│  │ decide_action(priority, user_status)                │      │
│  │   ├─ Available → none                               │      │
│  │   ├─ Busy + Urgent → remind                         │      │
│  │   └─ DND + Urgent → notify                          │      │
│  └──────────────────────────────────────────────────────┘      │
└────────────────────────────────────────────────────────────────┘
                              │
                              │ SQL
                              ▼
┌────────────────────────────────────────────────────────────────┐
│                    DATA LAYER                                   │
│                   SQLite Database                               │
│                     (nexa.db)                                   │
│                                                                  │
│  ┌──────────────────────┐  ┌──────────────────────┐            │
│  │    messages table    │  │    actions table     │            │
│  │ ─────────────────────│  │ ─────────────────────│            │
│  │ id (PRIMARY KEY)     │  │ id (AUTOINCREMENT)   │            │
│  │ platform             │  │ message_id (UNIQUE)  │            │
│  │ sender               │  │ action_type          │            │
│  │ content              │  │ priority             │            │
│  │ classification (JSON)│  │ status               │            │
│  │ classifier_used      │  │ action_data (JSON)   │            │
│  │ confidence           │  │ created_at           │            │
│  │ timestamp            │  │ executed_at          │            │
│  └──────────────────────┘  └──────────────────────┘            │
│                                                                  │
│  ┌──────────────────────┐  ┌──────────────────────┐            │
│  │   user_status table  │  │  message_cache table │            │
│  │ ─────────────────────│  │ ─────────────────────│            │
│  │ user_id (PRIMARY KEY)│  │ message_id (KEY)     │            │
│  │ status               │  │ platform             │            │
│  │ auto_reply_message   │  │ sender               │            │
│  │ updated_at           │  │ timestamp            │            │
│  └──────────────────────┘  └──────────────────────┘            │
└────────────────────────────────────────────────────────────────┘
                              │
                              │ External APIs
                              ▼
        ┌─────────────────────────────────────────┐
        │   External LLM Backends (Optional)      │
        │                                         │
        │  • Ollama (localhost:11435)             │
        │  • HuggingFace API (cloud)              │
        │  • Rule-based (fallback)                │
        └─────────────────────────────────────────┘
```

## Message Processing Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                   INCOMING MESSAGE                              │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ {                                                        │   │
│  │   "id": "msg_123",                                       │   │
│  │   "platform": "matrix",                                  │   │
│  │   "sender": "@user:example.com",                         │   │
│  │   "content": "URGENT: Server down!",                     │   │
│  │   "timestamp": 1234567890                                │   │
│  │ }                                                        │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│         STEP 1: CLASSIFICATION                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ MessageClassificationService.classify()                  │   │
│  │                                                          │   │
│  │ Input: "URGENT: Server down!"                           │   │
│  │                                                          │   │
│  │ Classification Chain:                                    │   │
│  │ 1. Try Ollama → Success (returns in <100ms)             │   │
│  │                                                          │   │
│  │ Output:                                                  │   │
│  │ {                                                        │   │
│  │   "priority": "urgent",                                  │   │
│  │   "category": "work",                                    │   │
│  │   "confidence": 0.85,                                    │   │
│  │   "reasoning": "Multiple urgent indicators",             │   │
│  │   "requires_action": true,                               │   │
│  │   "classifier_used": "ollama"                            │   │
│  │ }                                                        │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│         STEP 2: DECISION MAKING                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ ActionDecisionService.decide_action()                    │   │
│  │                                                          │   │
│  │ Input:                                                   │   │
│  │   priority: "urgent"                                     │   │
│  │   user_status: "available"                               │   │
│  │                                                          │   │
│  │ Decision Matrix:                                         │   │
│  │ ┌─────────────────────────────────────────────────────┐  │   │
│  │ │ Status: AVAILABLE                                 │  │   │
│  │ │   Priority: urgent → Action: none                 │  │   │
│  │ │         (User will see naturally)                 │  │   │
│  │ └─────────────────────────────────────────────────────┘  │   │
│  │                                                          │   │
│  │ Output: "none"                                           │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│         STEP 3: PERSISTENCE (DEDUPED)                           │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ DatabaseService.store_message()                          │   │
│  │                                                          │   │
│  │ INSERT INTO messages (                                   │   │
│  │   id="msg_123",                                          │   │
│  │   platform="matrix",                                     │   │
│  │   sender="@user:example.com",                            │   │
│  │   content="URGENT: Server down!",                        │   │
│  │   timestamp=1234567890,                                  │   │
│  │   classification=<JSON>,                                 │   │
│  │   classifier_used="ollama",                              │   │
│  │   confidence=0.85                                        │   │
│  │ ) OR IGNORE  ← Deduplication                             │   │
│  │                                                          │   │
│  │ Result: Message stored (first time) or ignored (dup)    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ DatabaseService.store_action()                           │   │
│  │                                                          │   │
│  │ INSERT INTO actions (                                    │   │
│  │   message_id="msg_123",  ← UNIQUE constraint             │   │
│  │   action_type="none",                                    │   │
│  │   priority="urgent",                                     │   │
│  │   status="PENDING",                                      │   │
│  │   classification_data=<JSON>                             │   │
│  │ )                                                        │   │
│  │                                                          │   │
│  │ Result: Action stored (1st time) or error (dup)         │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 RESPONSE SENT TO CLIENT                         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ {                                                        │   │
│  │   "status": "success",                                   │   │
│  │   "message_id": "msg_123",                               │   │
│  │   "action_id": 42,                                       │   │
│  │   "action_type": "none",                                 │   │
│  │   "priority": "urgent",                                  │   │
│  │   "classification": {                                    │   │
│  │     "priority": "urgent",                                │   │
│  │     "category": "work",                                  │   │
│  │     "confidence": 0.85,                                  │   │
│  │     "reasoning": "Multiple urgent indicators",           │   │
│  │     "requires_action": true,                             │   │
│  │     "classifier_used": "ollama"                          │   │
│  │   },                                                     │   │
│  │   "user_status": "available"                             │   │
│  │ }                                                        │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Classification Fallback Chain

```
┌──────────────────────────────────────────────────────┐
│  MessageClassificationService.classify()             │
│  Input: "URGENT: Help!"                              │
└──────────────────────────────────────────────────────┘
                    ▼
┌──────────────────────────────────────────────────────┐
│  Try: Ollama (Local LLM)                             │
│  ✓ Fast (<100ms)                                     │
│  ✓ Works offline                                     │
│  ✓ No API key needed                                 │
│  ─────────────────────────────────────────────────   │
│  POST http://localhost:11435/api/generate            │
│  {                                                   │
│    "model": "llama3.2:1b",                           │
│    "prompt": "[classification prompt]",              │
│    "stream": false,                                  │
│    "format": "json"                                  │
│  }                                                   │
│                                                      │
│  Success? ─────────────────────► Return Result      │
│  Fail? ─────┐                                        │
└──────────────┼──────────────────────────────────────┘
               ▼
┌──────────────────────────────────────────────────────┐
│  Try: HuggingFace Inference API                      │
│  ✓ Works in cloud                                    │
│  ✓ Better models available                          │
│  ✗ Requires API key                                  │
│  ✗ Slower (1-2s)                                     │
│  ─────────────────────────────────────────────────   │
│  POST https://api-inference.huggingface.co/...       │
│  Headers: Authorization: Bearer <HF_API_KEY>        │
│                                                      │
│  Success? ─────────────────────► Return Result      │
│  Fail? ─────┐                                        │
└──────────────┼──────────────────────────────────────┘
               ▼
┌──────────────────────────────────────────────────────┐
│  Fallback: Rule-Based Classification                │
│  ✓ Always works                                      │
│  ✓ Very fast (<1ms)                                  │
│  ✗ Less accurate                                     │
│  ─────────────────────────────────────────────────   │
│  Keywords Matching:                                  │
│  ├─ Urgent: "urgent", "asap", "down", "critical"   │
│  ├─ High: "deadline", "meeting", "client"          │
│  ├─ Work: "project", "work", "report"              │
│  └─ Low: Everything else                           │
│                                                      │
│  Always succeeds ──────────► Return Result          │
└──────────────────────────────────────────────────────┘
                    ▼
            Final Result Returned
            {
              priority: "urgent",
              classifier_used: "ollama"
            }
```

## Deduplication Mechanism

```
First Message Received:
┌──────────────────────────────────────────┐
│  message_id: "msg_123"                   │
│  content: "Hello"                        │
└──────────────────────────────────────────┘
                ▼
        DatabaseService
        store_message()
                ▼
        INSERT INTO messages
        (id="msg_123", ...)
                ▼
        ✅ Success (1 row inserted)
        Action stored with UNIQUE constraint


Second Message Received (Same ID):
┌──────────────────────────────────────────┐
│  message_id: "msg_123"  (DUPLICATE!)     │
│  content: "Hello"                        │
└──────────────────────────────────────────┘
                ▼
        DatabaseService
        store_message()
                ▼
        INSERT OR IGNORE INTO messages
        (id="msg_123", ...)
                ▼
        PRIMARY KEY violation!
                ▼
        ❌ Ignored (0 rows inserted)
        ✅ Returned as duplicate to caller


Response to Caller:
┌──────────────────────────────────────────┐
│  status: "duplicate"                     │
│  message_id: "msg_123"                   │
│  action: "none"                          │
└──────────────────────────────────────────┘

Benefits:
✓ No duplicate processing
✓ No wasted classification
✓ No duplicate actions
✓ O(1) detection (PRIMARY KEY lookup)
✓ Guaranteed by database (not application)
```

## Decision Matrix

```
┌─────────────────────────────────────────────────────────────┐
│              ACTION DECISION MATRIX                         │
├──────────┬───────────┬────────────┬─────────────────────────┤
│ Priority │ Available │ Busy       │ DND (Do Not Disturb)    │
├──────────┼───────────┼────────────┼─────────────────────────┤
│ URGENT   │ none      │ remind     │ notify                  │
│          │ (normal)  │ (later)    │ (BREAK THROUGH)         │
├──────────┼───────────┼────────────┼─────────────────────────┤
│ HIGH     │ none      │ remind     │ auto_reply              │
│          │ (normal)  │ (later)    │ (send auto-response)    │
├──────────┼───────────┼────────────┼─────────────────────────┤
│ NORMAL   │ none      │ none       │ auto_reply              │
│          │ (normal)  │ (ignore)   │ (send auto-response)    │
├──────────┼───────────┼────────────┼─────────────────────────┤
│ LOW      │ none      │ none       │ auto_reply              │
│          │ (normal)  │ (ignore)   │ (send auto-response)    │
└──────────┴───────────┴────────────┴─────────────────────────┘

Action Meanings:
• none:        No special action (user sees naturally)
• remind:      Remind user later (they're busy now)
• notify:      Send notification (break through DND)
• auto_reply:  Send automatic response to sender
```

## Thread Safety

```
┌────────────────────────────────────────┐
│  Concurrent Requests                   │
├────────────────────────────────────────┤
│  Request 1: process_message("msg1")    │
│  Request 2: process_message("msg2")    │
│  Request 3: get_statistics()           │
│  Request 4: update_user_status()       │
└────────────────────────────────────────┘
                ▼ (each to service)
        DatabaseService
        (all operations)
                ▼
        Global Lock (_lock)
        ┌────────────────────┐
        │  Thread 1 acquires │
        │  lock, executes    │
        │  SQL, releases     │
        └────────────────────┘
                ▼
        ┌────────────────────┐
        │  Thread 2 acquires │
        │  lock, executes    │
        │  SQL, releases     │
        └────────────────────┘
                ▼
        ┌────────────────────┐
        │  Thread 3 acquires │
        │  lock, executes    │
        │  SQL, releases     │
        └────────────────────┘

Result:
✓ All operations serialized
✓ No race conditions
✓ Data consistency guaranteed
✓ SQLite limitations respected (single writer)
```

## Files and Responsibilities

```
┌─────────────────────────────────────────────────────┐
│              PROJECT STRUCTURE                      │
├─────────────────────────────────────────────────────┤
│                                                     │
│  sidecar/main.py                                    │
│  └─ API Layer (FastAPI)                            │
│     ├─ POST /api/messages/classify                 │
│     ├─ POST /api/user/status                       │
│     ├─ GET /api/user/status                        │
│     ├─ GET /api/actions/pending                    │
│     ├─ GET /api/messages/recent                    │
│     ├─ GET /api/stats                              │
│     └─ GET /health                                 │
│                                                     │
│  sidecar/database.py                               │
│  └─ Data Layer (DatabaseService)                  │
│     ├─ store_message()                             │
│     ├─ store_action()                              │
│     ├─ get_message()                               │
│     ├─ get_action()                                │
│     ├─ get_statistics()                            │
│     ├─ update_action_status()                      │
│     ├─ update_user_status()                        │
│     └─ get_user_status()                           │
│                                                     │
│  sidecar/message_service.py                        │
│  └─ Service Layer                                   │
│     ├─ MessageClassificationService                │
│     │  └─ classify()                               │
│     ├─ ActionDecisionService                       │
│     │  └─ decide_action()                          │
│     └─ UnifiedMessageService                       │
│        └─ process_message()                        │
│                                                     │
│  sidecar/models.py                                 │
│  └─ Pydantic Data Models                           │
│     ├─ IncomingMessage                             │
│     ├─ Classification                              │
│     ├─ ActionResponse                              │
│     └─ UserStatus                                  │
│                                                     │
│  [Deprecated]                                      │
│  sidecar/db.py (moved to database.py)              │
│  sidecar/dedup.py (moved to database.py)           │
│                                                     │
└─────────────────────────────────────────────────────┘
```
