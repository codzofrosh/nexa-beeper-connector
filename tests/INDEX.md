# 📋 TEST SUITE INDEX & FILE GUIDE

## 🎯 What You Need to Know

This directory contains **three tier testing system** with complete documentation:
- **Tier 1** (5s): `verify.py` - Quick health check
- **Tier 2** (45s): `comprehensive_demo.py` - Full feature test  
- **Tier 3** (user-paced): `interactive_demo.py` - Manual exploration

---

## 📂 Files at a Glance

### 🚀 Start Here
- **START_HERE.md** - Quick navigation guide (READ THIS FIRST)
- **QUICK_REFERENCE.md** - One-page command reference

### 📊 Test Scripts
- **verify.py** - 5 tests in 5-10 seconds
- **comprehensive_demo.py** - 7 tests in 30-60 seconds
- **interactive_demo.py** - Real-time interactive testing
- **quickstart.py** - Menu to launch any demo

### 📖 Documentation  
- **DEMO_GUIDE.md** - Complete user guide (400 lines)
- **IMPLEMENTATION_SUMMARY.md** - Technical details
- **START_HERE.md** - Quick navigation
- **QUICK_REFERENCE.md** - Commands reference
- **INDEX.md** - This file

### 📝 Reference
- **test_demo.py** - Original demo (kept for reference)
- **README.md** - Basic script overview

---

## 🎮 Quick Commands

```bash
# Check if API works
python tests/verify.py

# Run full test suite
python tests/comprehensive_demo.py

# Interactive testing
python tests/interactive_demo.py

# Menu launcher
python tests/quickstart.py
```

---

## 📊 Comparison: Which Test to Use?

| Feature | verify | comprehensive | interactive |
|---------|--------|---------------|----|
| **Time** | 5-10s | 30-60s | Variable |
| **Tests** | 5 basic | 7 major | Manual |
| **Output** | ✓/✗ | Detailed | Real-time |
| **Best for** | CI/CD | Validation | Learning |

---

## 🧪 Tests Included

### verify.py (5 Tests)
1. API Health Check
2. Database Connectivity
3. Message Classification
4. User Status Management
5. Statistics Endpoint

### comprehensive_demo.py (7 Tests)
1. Message Classification (5 scenarios)
2. User Status Management
3. Action Decision Matrix
4. Deduplication
5. Pending Actions
6. Recent Messages
7. System Statistics

### interactive_demo.py (25+ Commands)
- 6 message commands
- 5 status commands
- 3 viewing commands
- 8 system commands

---

## 📚 Documentation Map

| Document | Purpose | Read Time |
|----------|---------|-----------|
| START_HERE.md | Quick navigation | 2 min |
| QUICK_REFERENCE.md | Command reference | 3 min |
| DEMO_GUIDE.md | Complete guide | 15 min |
| IMPLEMENTATION_SUMMARY.md | Technical specs | 10 min |

---

## 🎯 Choose Your Path

### Path 1: I Just Want Quick Check
```
1. Read: START_HERE.md (1 min)
2. Run: python tests/verify.py (10 sec)
3. Done!
```

### Path 2: I Want Full Validation
```
1. Read: QUICK_REFERENCE.md (3 min)
2. Run: python tests/comprehensive_demo.py (45 sec)
3. Read: DEMO_GUIDE.md (optional, 15 min)
```

### Path 3: I Want to Explore
```
1. Read: START_HERE.md (1 min)
2. Run: python tests/interactive_demo.py
3. Try commands: send, stats, available, help
```

### Path 4: I Want Complete Understanding
```
1. Read: START_HERE.md (1 min)
2. Run: python tests/verify.py (10 sec)
3. Run: python tests/comprehensive_demo.py (45 sec)
4. Read: DEMO_GUIDE.md (15 min)
5. Read: IMPLEMENTATION_SUMMARY.md (10 min)
6. Run: python tests/interactive_demo.py (20 min)
```

---

## 🚀 Typical Usage

### First Time Setup
```bash
# Terminal 1: Start sidecar
python sidecar/main.py

# Terminal 2: Verify it works
python tests/verify.py

# Terminal 2: Explore features
python tests/interactive_demo.py
```

### Regular Testing
```bash
# Quick check
python tests/verify.py

# Full validation before deployment
python tests/comprehensive_demo.py
```

### Detailed Exploration
```bash
python tests/interactive_demo.py
> help        # See all commands
> stats       # Show statistics
> actions     # Show pending actions
```

---

## 🎨 Understanding Output

### Color Codes
```
🟢 [✓] Green   = Success / OK
🔴 [✗] Red     = Error / Problem
🔵 [i] Blue    = Information
🟡 [!] Yellow  = Warning
🟦 Cyan        = Section headers
```

### Result Fields
```
Priority:    urgent | high | normal | low
Action:      immediate | defer | auto_reply | ignore
Confidence:  0% - 100% (how sure is the classifier)
Classifier:  ollama | huggingface | rules (which engine)
Status:      new | duplicate
```

---

## 🔧 Troubleshooting Quick Lookup

| Problem | Solution |
|---------|----------|
| "Cannot connect to API" | Run `python sidecar/main.py` first |
| "Slow classification" | Normal for first message (LLM thinking) |
| "Ollama not available" | Falls back to HuggingFace automatically |
| "Database error" | Delete `data/nexa.db` and restart |
| "Port 8000 in use" | Check if sidecar already running |

See **DEMO_GUIDE.md** Troubleshooting section for more.

---

## 📞 Need Help?

| Question | Answer In |
|----------|-----------|
| "How do I start?" | START_HERE.md |
| "What commands exist?" | QUICK_REFERENCE.md |
| "How does feature X work?" | DEMO_GUIDE.md |
| "What's under the hood?" | IMPLEMENTATION_SUMMARY.md |
| "How do I fix error Y?" | DEMO_GUIDE.md (Troubleshooting) |

---

## 📂 File Descriptions

### verify.py (95 lines)
Quick API health check with 5 tests. Best for CI/CD and automated testing.
```bash
python tests/verify.py
# Output: ✓/✗ indicators for each test
```

### comprehensive_demo.py (450 lines)
Complete test suite with 7 feature areas and detailed output.
```bash
python tests/comprehensive_demo.py
# Output: Colored, formatted results with explanations
```

### interactive_demo.py (450 lines)
Real-time interactive CLI with 25+ commands for manual exploration.
```bash
python tests/interactive_demo.py
# Input: Your commands
# Output: Real-time results
```

### quickstart.py (100 lines)
Menu launcher to choose which demo to run.
```bash
python tests/quickstart.py
# Choose: 1-5 (or read docs)
```

### START_HERE.md
Quick navigation guide and delivery summary.

### QUICK_REFERENCE.md
One-page command and troubleshooting reference.

### DEMO_GUIDE.md
Comprehensive 400-line user guide with examples and troubleshooting.

### IMPLEMENTATION_SUMMARY.md
Technical specifications and architecture integration details.

---

## 🎯 Success Path

✅ **Step 1**: You read this file (INDEX.md) - **DONE**
⏭️ **Step 2**: Read START_HERE.md (1 minute)
⏭️ **Step 3**: Run `python tests/verify.py` (10 seconds)
⏭️ **Step 4**: Run `python tests/interactive_demo.py` (10 minutes)
⏭️ **Step 5**: Read DEMO_GUIDE.md (optional)

---

## 📊 Statistics

| Metric | Value |
|--------|-------|
| Total Scripts | 4 |
| Total Documentation | 5 files, ~1,200 lines |
| Test Coverage | 7 major features |
| Commands | 25+ in interactive |
| API Endpoints | 7 total |
| Line of Code | ~1,200 (scripts + docs) |

---

## ✨ Highlights

- ✅ Three-tier testing (5s, 45s, interactive)
- ✅ Beautiful colored terminal output
- ✅ 25+ interactive commands
- ✅ Comprehensive documentation
- ✅ Real-time statistics viewing
- ✅ Debug mode included
- ✅ Error handling built-in
- ✅ Cross-platform support

---

## 🚀 Get Started Now!

### Option 1: Super Quick (1 min)
```bash
python tests/verify.py
```

### Option 2: Interactive (10 min)
```bash
python tests/interactive_demo.py
> help
> send Test message
> stats
```

### Option 3: Full Check (1 hour)
```bash
python tests/quickstart.py
# Choose option 5 for full sequence
```

---

**👉 Next: Read [START_HERE.md](START_HERE.md)**
