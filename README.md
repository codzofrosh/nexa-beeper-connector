Nexa Beeper Connector
======================

Description
-----------
Nexa Beeper Connector is an intelligent message routing system that listens for messages (e.g., from Matrix, WhatsApp), classifies them using AI/ML models, decides appropriate actions, persists those actions, and exposes APIs for inspection and management. 

The system is designed to be lightweight, self-contained, and easily deployable in local or small-scale environments.

Key Features
------------
- **Login & Session Auth Starter**: Browser-based login/register page with name, email, password, and sidecar session cookies
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
    - Auth UI: `GET /` and `GET /login`
    - Auth APIs: `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/logout`
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
- `MATRIX_HOMESERVER`: Matrix homeserver base URL for bot/client mode
- `MATRIX_ACCESS_TOKEN`: Matrix access token for bot/client mode
- `MATRIX_USER`: Matrix user ID for the bot/client
- `MAUTRIX_HOMESERVER`: Preferred homeserver base URL for bridge execution mode
- `MAUTRIX_ACCESS_TOKEN`: Preferred access token for bridge execution mode
- `MAUTRIX_IMPERSONATE_USER_ID`: Optional appservice user ID to masquerade as when sending into bridged rooms
- `MAUTRIX_DEVICE_ID`: Optional device ID to include when using application-service identity assertion

Mautrix / bridge execution
--------------------------
The bridge executor sends outbound messages by posting `m.room.message` events
to Matrix rooms. When those rooms are bridged by mautrix-whatsapp, the bridge
forwards the messages to WhatsApp.

The outbound adapter supports two authentication modes:

1. **Bot/client token mode**
   - set `MATRIX_HOMESERVER` + `MATRIX_ACCESS_TOKEN`, or
   - set `MAUTRIX_HOMESERVER` + `MAUTRIX_ACCESS_TOKEN`

2. **Application-service masquerading mode**
   - set `MAUTRIX_HOMESERVER`
   - set `MAUTRIX_ACCESS_TOKEN` to the appservice token
   - set `MAUTRIX_IMPERSONATE_USER_ID` to the Matrix user ID the appservice
     should send as
   - optionally set `MAUTRIX_DEVICE_ID`

In both cases, the bridge uses Matrix transaction IDs for idempotent sends, so
the same executor retry will reuse the same `txnId`.

API Endpoints
-------------
**Classification**
- `POST /api/messages/classify` - Classify a message
  - Returns: priority, action type, classification details

**Authentication**
- `GET /` or `GET /login` - Login/register page
- `POST /api/auth/register` - Create account with name, email, password
- `POST /api/auth/login` - Login with email and password
- `GET /api/auth/me` - Read current session user
- `POST /api/auth/logout` - Clear current session

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
