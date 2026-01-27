# Test & Demo Suite - Nexa Beeper Sidecar

This directory contains comprehensive test and demo scripts to verify and demonstrate the functionality of the Nexa Beeper Sidecar service.

## Quick Start

### 1. Verify Installation
Before running tests, ensure the sidecar service is running:

```bash
# Terminal 1 - Start the sidecar
python sidecar/main.py

# Terminal 2 - Run verification
python tests/verify.py
```

If all tests pass, you're ready to run demos!

## Available Scripts

### `verify.py` - Quick Health Check ⚡
**Purpose**: Fast API connectivity verification

**Features**:
- Tests API health endpoint
- Verifies database connectivity
- Tests message classification
- Verifies user status management
- Checks statistics endpoint

**Usage**:
```bash
python tests/verify.py
```

**What it does**: 
- Runs 5 basic tests in ~5 seconds
- Shows which endpoints are working
- Quick go/no-go decision

---

### `comprehensive_demo.py` - Full Feature Test Suite 📊
**Purpose**: Comprehensive testing of all system features

**Tests**:
1. **Message Classification** - Tests LLM classification with various priorities
2. **User Status Management** - Tests available/busy/dnd status changes
3. **Action Decision Matrix** - Tests how actions change based on user status
4. **Deduplication** - Verifies duplicate messages are caught
5. **Pending Actions** - Retrieves and displays pending actions
6. **Recent Messages** - Shows database message history
7. **System Statistics** - Displays aggregated stats

**Usage**:
```bash
python tests/comprehensive_demo.py
```

**Sample Output**:
```
═══════════════════════════════════════════════════════════════════════════
  NEXA BEEPER SIDECAR - COMPREHENSIVE TEST SUITE
═══════════════════════════════════════════════════════════════════════════

═══════════════════════════════════════════════════════════════════════════
  PREREQUISITES: API HEALTH CHECK
═══════════════════════════════════════════════════════════════════════════
[OK] API is running and healthy
  Service: nexa-sidecar
  Ollama: Available
  Database: data/nexa.db

[Test 1: MESSAGE CLASSIFICATION]
  Message: 'URGENT: Production server is down!'
    Priority: urgent (expected: urgent)
    Confidence: 89.50%
    Classifier: ollama
    Action: immediate
    Status: new
[OK] Classification correct
```

**Time**: ~30-60 seconds (depending on LLM responsiveness)

---

### `interactive_demo.py` - Real-Time Interactive Demo 🎮
**Purpose**: Live, interactive testing with user input

**Features**:
- Send custom messages for real-time classification
- Change user status and watch action decisions change
- View system statistics and pending actions
- Browse message history
- Monitor message deduplication
- Beautiful colored output with command prompts

**Usage**:
```bash
python tests/interactive_demo.py
```

**Available Commands**:

#### Message Commands
- `send <message>` - Send a message for classification
- `history` - Show all messages sent in this session
- `clear_history` - Clear session history

#### User Status Commands
- `status` - Show current user status
- `available` - Set status to available
- `busy` - Set status to busy
- `dnd` - Set status to do-not-disturb (do-not-disturb)

#### Data Viewing
- `stats` - Show system statistics (total messages, priorities, classifiers)
- `actions` - Show pending actions (with IDs and priorities)
- `messages` - Show recent messages from database

#### System Commands
- `health` - Check API health status
- `verbose` - Toggle verbose output mode
- `debug` - Toggle debug output (shows full responses)
- `clear` - Clear the screen
- `help` - Show command help
- `exit` - Exit the program

**Example Session**:
```
[interactive_user | available] > send URGENT: The server is down!
[i] Sending message: 'URGENT: The server is down!'

═══════════════════════════════════════════════════════════════════════════
  Classification Result
═══════════════════════════════════════════════════════════════════════════
  Priority:      urgent
  Action:        immediate
  Status:        new

  Classification Details:
    Classifier:  ollama
    Confidence:  92.5%
    Reasoning:   Keyword detection: URGENT, emergency keywords...

  Action ID:     act_1705123456789

[✓] Message processed successfully

[interactive_user | available] > busy
[✓] Status changed to: busy

[interactive_user | busy] > send Can we meet tomorrow?
[✓] Message processed successfully

[interactive_user | busy] > stats
═══════════════════════════════════════════════════════════════════════════
  System Statistics
═══════════════════════════════════════════════════════════════════════════
  Total Messages:      2
  Pending Actions:     2

  Priority Breakdown:
    high      : 1
    urgent    : 1

  Classifiers Used:
    ollama            : 2

  Config:
    Ollama Enabled:  True
    Classifier:      hybrid

[interactive_user | busy] > exit
[i] Goodbye!
```

---

## Testing Workflows

### Test 1: Basic Classification Testing
**Goal**: Verify classification system works

```bash
# Terminal 1: Start sidecar
python sidecar/main.py

# Terminal 2: Run quick test
python tests/verify.py

# Terminal 3: Interactive testing
python tests/interactive_demo.py
> send This is a test message
> send URGENT: Help needed immediately!
> stats
> exit
```

### Test 2: User Status Impact Testing
**Goal**: Verify status changes affect action decisions

```bash
python tests/interactive_demo.py
> available
> send Can we catch up later?
> stats
> dnd
> send URGENT ISSUE
> stats
> exit
```

### Test 3: Deduplication Testing
**Goal**: Verify duplicate messages are detected

```bash
python tests/comprehensive_demo.py
# Watch for TEST 4: DEDUPLICATION section
# Shows first send and duplicate detection
```

### Test 4: Full System Verification
**Goal**: Comprehensive system check

```bash
# Run all tests in sequence
python tests/verify.py
python tests/comprehensive_demo.py
python tests/interactive_demo.py
```

---

## Understanding the Output

### Color Codes
- 🟢 **Green** `[✓]` - Success / Working correctly
- 🔴 **Red** `[✗]` - Error / Problem detected
- 🔵 **Blue** `[i]` - Information
- 🟡 **Yellow** `[!]` - Warning / Unexpected but handled
- 🟦 **Cyan** - Section headers

### Response Fields Explained

**Priority Levels**:
- `urgent` - Immediate action needed
- `high` - Important, needs prompt handling
- `normal` - Regular message
- `low` - Low priority

**Action Types**:
- `immediate` - Respond now
- `defer` - Handle when available
- `auto_reply` - Send auto-response
- `ignore` - Defer/archive
- `none` - No action needed

**Classifiers**:
- `ollama` - Local LLM model (fastest, most accurate)
- `huggingface` - Cloud LLM (fallback to local if down)
- `rules` - Keyword-based (always works, less accurate)

**Status**:
- `new` - First time seeing this message
- `duplicate` - Message already processed

---

## Troubleshooting

### "Cannot connect to API"
```bash
# Make sure sidecar is running
python sidecar/main.py

# Check if it's listening
curl http://localhost:8000/health
```

### "Ollama is not available"
```bash
# This is expected if Ollama isn't installed
# Classification will fall back to HuggingFace or rules
# Check sidecar logs for details
```

### "Database error"
```bash
# Delete old database and recreate
rm data/nexa.db

# Restart sidecar (it will recreate schema)
python sidecar/main.py
```

### Slow classification (>10 seconds)
```bash
# Local LLM is thinking - this is normal for first message
# Subsequent messages should be faster
# You can enable debug mode to see timing:
python tests/interactive_demo.py
> debug
> send Test message
```

---

## Performance Expectations

| Test | Duration | Notes |
|------|----------|-------|
| `verify.py` | 5-10s | Quick connectivity check |
| `comprehensive_demo.py` | 30-60s | Depends on LLM speed |
| `interactive_demo.py` | Variable | User-controlled |

---

## Architecture Context

See [ARCHITECTURE.md](../ARCHITECTURE.md) for detailed system design.

Key points for testing:
- **Unified Pipeline**: Messages go through classification → decision → persistence in single atomic operation
- **Multi-Backend Classification**: Ollama (local) → HuggingFace (cloud) → Rules (fallback)
- **Thread-Safe Database**: All DB operations protected by locks
- **Automatic Deduplication**: SQL constraints prevent duplicate storage

---

## Next Steps

After running these tests:

1. **Review ARCHITECTURE.md** - Understand system design
2. **Check QUICK_REFERENCE.md** - API endpoint reference
3. **Deploy to Production** - Use Docker: `docker-compose up`
4. **Monitor Metrics** - See DIAGRAMS.md for monitoring setup

---

## Script Files Reference

```
tests/
├── verify.py              # Quick health check (5-10s)
├── comprehensive_demo.py  # Full feature test (30-60s)
├── interactive_demo.py    # Interactive real-time (user-paced)
├── test_demo.py          # Original demo (kept for reference)
├── README.md             # This file
└── run_demo.sh           # Bash script runner (if needed)
```

---

**Last Updated**: 2024
**Compatible With**: Nexa 2.0 Refactored Architecture
