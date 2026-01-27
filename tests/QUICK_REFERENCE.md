# Demo Scripts - Quick Reference Card

## Start Here 🚀

```bash
# 1. Ensure sidecar is running
python sidecar/main.py

# 2. In another terminal, choose one:

# Quick check (5-10 seconds)
python tests/verify.py

# Full test (30-60 seconds)
python tests/comprehensive_demo.py

# Interactive mode (user-paced)
python tests/interactive_demo.py

# Or use the menu
python tests/quickstart.py
```

---

## Quick Reference

### verify.py
| What | Command |
|------|---------|
| **Run** | `python tests/verify.py` |
| **Time** | 5-10 seconds |
| **Best for** | Quick API health check |
| **Tests** | 5 basic endpoints |
| **Output** | ✓/✗ indicators |

### comprehensive_demo.py
| What | Command |
|------|---------|
| **Run** | `python tests/comprehensive_demo.py` |
| **Time** | 30-60 seconds |
| **Best for** | Full feature validation |
| **Tests** | 7 major features |
| **Output** | Detailed results |

### interactive_demo.py
| What | Command |
|------|---------|
| **Run** | `python tests/interactive_demo.py` |
| **Time** | User-controlled |
| **Best for** | Exploring features |
| **Tests** | Manual exploration |
| **Output** | Real-time feedback |

---

## Interactive Demo Commands

### Sending Messages
```
send URGENT: Help!          → Classify message
send Normal message         → Test normal priority
history                     → Show sent messages
clear_history              → Clear history
```

### Changing Status
```
available                  → Set to available
busy                      → Set to busy
dnd                       → Set to do-not-disturb
status                    → Show current status
```

### Viewing Data
```
stats                     → System statistics
actions                   → Pending actions
messages                  → Recent messages
```

### System
```
health                    → Check API status
verbose                   → Toggle verbose mode
debug                     → Toggle debug mode
clear                     → Clear screen
help                      → Show all commands
exit                      → Quit
```

---

## Expected Behavior

### Classification Output
```
Priority:   urgent | high | normal | low
Action:     immediate | defer | auto_reply | ignore
Confidence: 0-100%
Classifier: ollama | huggingface | rules
```

### Status Impact
```
Available + URGENT   → Action: immediate
Busy + URGENT        → Action: defer + auto_reply
DND + URGENT         → Action: defer (quiet mode)
```

### Deduplication
```
First message  → Status: new
Same message   → Status: duplicate
Different msg  → Status: new
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Cannot connect to API" | Run `python sidecar/main.py` first |
| "Slow classification" | Normal for first message (LLM thinking) |
| "Ollama not available" | Falls back to HuggingFace automatically |
| "Database error" | Delete `data/nexa.db` and restart sidecar |
| "Port already in use" | Change API_URL in script or stop other service |

---

## Example Workflows

### Test 1: Classification Accuracy (2 min)
```bash
python tests/interactive_demo.py
> send The server crashed!
> send Can we meet tomorrow?
> send CRITICAL PRODUCTION DOWN
> exit
```

### Test 2: Status Impact (3 min)
```bash
python tests/interactive_demo.py
> available
> send URGENT: help
> busy
> send URGENT: help
> dnd
> send URGENT: help
> stats
> exit
```

### Test 3: Full Verification (5 min)
```bash
python tests/verify.py
# Wait for results
python tests/comprehensive_demo.py
# Watch all 7 tests
```

---

## Important Files

| File | Purpose |
|------|---------|
| `verify.py` | Quick health check |
| `comprehensive_demo.py` | Full test suite |
| `interactive_demo.py` | Manual exploration |
| `quickstart.py` | Menu launcher |
| `DEMO_GUIDE.md` | Detailed documentation |
| `IMPLEMENTATION_SUMMARY.md` | Technical details |

---

## API Endpoints Being Tested

| Endpoint | Method | Tests |
|----------|--------|-------|
| `/health` | GET | API availability |
| `/api/messages/classify` | POST | Classification |
| `/api/user/status` | POST | Status updates |
| `/api/user/status` | GET | Status retrieval |
| `/api/stats` | GET | Statistics |
| `/api/actions/pending` | GET | Actions |
| `/api/messages/recent` | GET | Messages |

---

## Next Steps After Testing

1. ✅ Run `verify.py` → Confirm API works
2. ✅ Run `comprehensive_demo.py` → Verify all features
3. ✅ Run `interactive_demo.py` → Explore manually
4. 📖 Read `DEMO_GUIDE.md` → Understand details
5. 📖 Read `ARCHITECTURE.md` → Learn system design
6. 🚀 Deploy to production → Use Docker Compose

---

## Color Meanings

- 🟢 **Green** `[✓]` = Success / OK
- 🔴 **Red** `[✗]` = Error / Problem
- 🔵 **Blue** `[i]` = Information
- 🟡 **Yellow** `[!]` = Warning
- 🟦 **Cyan** = Sections / Headers

---

## Pro Tips

1. Use `verbose` mode to see detailed responses
2. Use `debug` mode to see raw API responses
3. Use `history` in interactive mode to review past messages
4. Use `stats` to verify message counts increasing
5. Try changing status before sending URGENT messages
6. Watch how `actions` list grows with pending items

---

**For detailed information, see DEMO_GUIDE.md**
