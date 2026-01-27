Nexa Beeper Connector
======================

Description
-----------
Nexa Beeper Connector is an intelligent message routing system that listens for messages (e.g., from Matrix, WhatsApp), classifies them using AI/ML models, decides appropriate actions, persists those actions, and exposes APIs for inspection and management. 

The system is designed to be lightweight, self-contained, and easily deployable in local or small-scale environments.

Key Features
------------
- **AI-Powered Message Classification**: Classifies messages by priority (urgent, high, normal, low) and category (work, personal, social, marketing)
- **Multi-Backend LLM Support**: Supports Ollama (local), OpenAI, Anthropic Claude, Hugging Face, or custom API backends
- **Flexible Fallback System**: Rule-based classification falls back when LLMs are unavailable
- **User Status Management**: Track user availability (available, busy, do-not-disturb) with auto-responses
- **Action Decision Engine**: Decides what action to take based on classification and user status
- **RESTful API**: Complete HTTP API for classification, status management, and metrics
- **Persistent Storage**: SQLite database for messages, actions, and user state
- **Real-time Interactive CLI**: Test the system with interactive message input

Directory roles
---------------
- **ai/**
  - Contains the AI pipeline: classification modules, normalization, and policy decision code
  - `classifier.py`: Base classifier interface
  - `cloud_classifier.py`: Cloud-based LLM classifiers (OpenAI, Anthropic, HuggingFace, custom APIs)
  - `local_model.py`: Local model support
  - `rule_based.py`: Rule-based fallback classifier
  - `pipeline.py`: Orchestrates classification pipeline

- **sidecar/**
  - Main FastAPI service that handles message classification
  - Accepts messages via HTTP API, runs classification, stores results
  - Provides endpoints for:
    - Message classification: `POST /api/messages/classify`
    - User status management: `GET/POST /api/user/status`
    - Pending actions: `GET /api/actions/pending`
    - Recent messages: `GET /api/messages/recent`
    - System stats: `GET /api/stats`
    - Health check: `GET /health`

- **bridge/**
  - Execution bridge that processes pending actions
  - Claims actions, executes them (notify, escalate, etc.)
  - Maintains cursor for ordered processing and restart resilience
  - Database integration and idempotency handling

- **tests/**
  - Integration tests and demo scripts
  - `test_demo.py`: Automated demo showing different user statuses
  - `interactive_demo.py`: Interactive CLI for real-time testing
  - End-to-end workflow testing

- **config/**
  - Application configuration and settings

Configuration
--------------
Environment variables:
- `OLLAMA_URL`: Ollama server URL (default: http://localhost:11435)
- `OLLAMA_MODEL`: Model to use with Ollama (default: llama3.2:1b)
- `USE_OLLAMA`: Enable Ollama (default: true)
- `HF_API_KEY`: Hugging Face API key for cloud classification
- `DB_PATH`: SQLite database path (default: data/nexa.db)

API Endpoints
-------------
**Classification**
- `POST /api/messages/classify` - Classify a message
  - Returns: priority, action type, classification details

**User Status**
- `GET /api/user/status?user_id=default_user` - Get user status
- `POST /api/user/status` - Update user status (available/busy/dnd)

**Actions & Messages**
- `GET /api/actions/pending` - Get pending actions
- `GET /api/messages/recent?limit=20` - Get recent messages

**Metrics**
- `GET /api/stats` - Get system statistics
- `GET /health` - Health check

Quick Start
-----------
1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Start Ollama** (optional, for local LLM):
   ```bash
   ollama serve
   ```

3. **Run the sidecar service**:
   ```bash
   python sidecar/main.py
   ```
   Server starts at `http://localhost:8000`

4. **Test with interactive demo**:
   ```bash
   python tests/interactive_demo.py
   ```

5. **Or run automated demo**:
   ```bash
   python tests/test_demo.py
   ```

Interactive Demo Commands
--------------------------
Once running `python tests/interactive_demo.py`:
- Type any message → instant classification
- `status` → show current user status
- `available` / `busy` / `dnd` → change status
- `stats` → show system statistics
- `help` → show all commands
- `quit` / `exit` → exit

Example:
```
> Hey, can we meet tomorrow?
[Classification: normal priority, personal]

> URGENT: Production server down!!!
[Classification: urgent priority, work]

> status
[Current status: available]

> busy
[Status changed to busy]
```

Database Schema
---------------
- **messages**: Stores incoming messages with classification results
- **actions**: Stores pending/executed actions per message
- **user_status**: Tracks user availability and auto-reply settings

Notes
-----
- The project uses SQLite for lightweight persistence, ideal for local deployments
- Multiple classification backends allow upgrading AI capabilities without changing code
- Backward-compatible schema migrations avoid breaking development environments
- All components are designed to be independently testable and replaceable

Contributing
------------
- Add or update tests when changing behavior around classification, persistence, or execution
- If modifying DB schema, add migration tests to the `tests/` directory
- Follow the modular design: classifier implementations should be swappable

Project Status
--------------
Branch: `Integrating_classifier`
Currently integrating cloud-based LLM classifiers (OpenAI, Claude, HuggingFace) with local Ollama fallback
