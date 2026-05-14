# Nexa — AI Message Router for WhatsApp, LinkedIn, Instagram & X

An AI-powered message routing system that receives DMs from WhatsApp, LinkedIn, Instagram, and X (Twitter) via a self-hosted Matrix stack, classifies them with LLMs, and executes smart actions (notify, escalate, suppress).

---

## How it works

```
WhatsApp  ─┐
LinkedIn  ─┤
           ├─▶ mautrix bridges ─▶ Synapse (Matrix) ─▶ nexa-sidecar ─▶ classify ─▶ decide ─▶ store ─▶ executor
Instagram ─┤
X/Twitter ─┘
```

1. Messages arrive on any of the four platforms
2. mautrix bridges forward them as Matrix events to Synapse
3. The nexa-sidecar receives the events, classifies them with AI, and stores an action
4. The executor delivers responses back through the bridge

---

## Stack

| Service | Image | Purpose |
|---|---|---|
| `conduit` | `ghcr.io/element-hq/synapse:latest` | Matrix homeserver (Synapse) |
| `mautrix-whatsapp` | `dock.mau.dev/mautrix/whatsapp:latest` | WhatsApp ↔ Matrix bridge |
| `mautrix-linkedin` | `dock.mau.dev/mautrix/linkedin:latest` | LinkedIn ↔ Matrix bridge |
| `mautrix-instagram` | `dock.mau.dev/mautrix/meta:latest` | Instagram DMs ↔ Matrix bridge |
| `mautrix-twitter` | `dock.mau.dev/mautrix/twitter:latest` | X (Twitter) DMs ↔ Matrix bridge |
| `nexa-sidecar` | local build | AI classification + REST API |
| `nexa-frontend` | `ghcr.io/codzofrosh/nexa-frontend:latest` | React UI (nginx on port 80) |

---

## Quick start

**Prerequisites:** Docker Desktop running, Python 3.10+

```bash
# 1. Clone and install Python deps
git clone https://github.com/codzofrosh/nexa-beeper-connector.git
cd nexa-beeper-connector
pip install -r requirements.txt

# 2. One-time setup (generates configs, registers admin, starts all services)
python bridge/auth/setup.py

# 3. The full stack is now running
#    UI:           http://localhost  (nginx → React frontend)
#    Sidecar API:  http://localhost:8080
#    Swagger:      http://localhost:8080/docs
#    Matrix:       http://localhost:6167
```

`setup.py` is idempotent — safe to re-run.

### What setup.py does

1. Generates appservice registration files for all four bridges
2. Generates `bridge/synapse/homeserver.yaml` with fresh secrets (includes all 4 registrations)
3. Starts Synapse, waits for it to be ready
4. Registers `@admin:localhost` as a Synapse server admin
5. Starts all four mautrix bridges and the nexa-sidecar

---

## User onboarding

### WhatsApp — QR code

```
POST /api/onboard/whatsapp/start
Body: { "user_id": "alice" }

→ Returns session_id + QR code (base64 PNG)
→ User scans QR in WhatsApp → Linked devices → Link a device
→ Poll GET /api/onboard/whatsapp/status/{session_id} every 3s until "connected"
```

### LinkedIn — cURL cookies

1. DM `@linkedinbot:localhost` in a Matrix client
2. Send: `login`
3. Open LinkedIn in your browser → DevTools → Network tab → find any GraphQL XHR request → right-click → **Copy as cURL**
4. Paste the cURL command to the bridge bot

### Instagram — session cookie

1. DM `@instagrambot:localhost` in a Matrix client
2. Send: `login`
3. Open `instagram.com` → DevTools → Application → Cookies
4. Copy the `sessionid` cookie value and paste it to the bridge bot

### X (Twitter) — auth cookies

1. DM `@twitterbot:localhost` in a Matrix client
2. Send: `login`
3. Open `x.com` → DevTools → Application → Cookies
4. Copy the `auth_token` and `ct0` values and paste them to the bridge bot

---

## Authentication

The sidecar has its own user accounts (separate from Matrix accounts).

| Method | Endpoint |
|---|---|
| Email + password register | `POST /api/auth/register` |
| Email + password login | `POST /api/auth/login` |
| Sign in with Google | `GET /api/auth/oauth/google/start` |
| Sign in with GitHub | `GET /api/auth/oauth/github/start` |

All auth sets an `HttpOnly` session cookie (`nexa_session`, 24h TTL).  
Include `credentials: 'include'` in all browser `fetch()` calls.

---

## API reference

| URL | What |
|---|---|
| `http://localhost/` | React frontend (login, dashboard, bridges) |
| `http://localhost:8080/dev` | Frontend developer guide — all endpoints with examples and a copy-paste JS client |
| `http://localhost:8080/docs` | Swagger UI — interactive, try any endpoint live |
| `http://localhost:8080/redoc` | ReDoc — clean read-only reference |

### Endpoint groups

**Auth** — register, login, logout, OAuth (Google / GitHub), session check

**Onboarding** — WhatsApp QR flow (`/api/onboard/whatsapp/*`)

**Bridge** — connect / disconnect any platform (`/api/bridge/{platform}/*`)  
Supported platforms: `whatsapp`, `linkedin`, `instagram`, `twitter`

**Messages** — classify incoming messages, retrieve history (`/api/messages/*`)

**User** — availability status, pending actions (`/api/user/status`, `/api/actions/pending`)

**System** — health check (`/health`), statistics (`/api/stats`)

---

## AI classification

Messages are classified into:

| Label | Action |
|---|---|
| `ENQUIRY` | NOTIFY |
| `INTENT` | ESCALATE |
| `PROMOTION` | IGNORE |
| `SOCIAL` | IGNORE |

Three-tier fallback:

1. **Ollama** (local) — `llama3.2:1b` by default, configurable via `OLLAMA_MODEL`
2. **HuggingFace** (cloud) — `Mistral-7B-Instruct-v0.2`
3. **Rule-based** — regex fallback, always works offline

---

## Environment variables

```env
# Matrix
MATRIX_HOMESERVER=http://conduit:8008
MATRIX_SERVER_NAME=localhost
MATRIX_USER=@admin:localhost
MATRIX_ACCESS_TOKEN=<generated by setup.py>

# Bridge bots (auto-resolved from MATRIX_SERVER_NAME if not set)
WHATSAPP_BRIDGE_BOT=@whatsappbot:localhost
LINKEDIN_BRIDGE_BOT=@linkedinbot:localhost
INSTAGRAM_BRIDGE_BOT=@instagrambot:localhost
TWITTER_BRIDGE_BOT=@twitterbot:localhost

# CORS — comma-separated allowed origins for the browser frontend
ALLOWED_ORIGINS=http://localhost,http://localhost:3000

# AI (optional — falls back to rule-based if not set)
OLLAMA_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama3.2:1b
HF_API_KEY=

# OAuth (optional — omit to disable social login buttons)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
OAUTH_REDIRECT_BASE_URL=http://localhost:8080

# Sidecar
DB_PATH=/data/nexa.db
AUTH_SESSION_TTL_HOURS=24
```

All values except OAuth credentials are auto-populated in `.env` by `setup.py`.

---

## Project layout

```
bridge/
  auth/
    setup.py              — one-time infrastructure setup (all 4 bridges)
  synapse/
    homeserver.yaml       — generated Synapse config
    logging.yaml          — Synapse log config
  whatsapp/
    config.yaml           — mautrix-whatsapp config (generated)
    whatsapp-registration.yaml
  linkedin/
    config.yaml           — mautrix-linkedin config (generated)
    linkedin-registration.yaml
  instagram/
    config.yaml           — mautrix-meta config, mode=instagram (generated)
    instagram-registration.yaml
  twitter/
    config.yaml           — mautrix-twitter config (generated)
    twitter-registration.yaml
  adapters/
    mautrix.py            — MautrixSender: sends Matrix messages back to bridges
  executor/
    loop.py               — executor_loop: claim → execute → retry with backoff

sidecar/
  main.py                 — FastAPI app, all HTTP endpoints
  database.py             — DatabaseService: thread-safe SQLite
  message_service.py      — classification + action decision pipeline
  auth.py                 — PBKDF2-SHA256 password hashing, session tokens
  oauth.py                — Google and GitHub OAuth2 flows
  onboarding.py           — WhatsApp QR onboarding via Matrix DM
  dev_guide.py            — HTML developer guide served at /dev

nginx.conf                — nginx reverse proxy (serves frontend, proxies /api/*)
docker-compose.yaml       — full stack definition (6 services + 5 volumes)
ec2-setup.sh              — EC2 bootstrap script (Ubuntu 22.04)
app.py                    — Matrix event listener (matrix-nio)
```

---

## Docker commands

```bash
# Start everything
docker compose up -d

# Rebuild sidecar after code changes
docker compose up -d --build nexa-sidecar

# Pull latest frontend image (built by Nexa-FrontEnd repo CI)
docker compose pull nexa-frontend && docker compose up -d nexa-frontend

# View logs for a specific service
docker compose logs -f nexa-sidecar
docker compose logs -f mautrix-instagram

# Stop everything
docker compose down

# Full reset (deletes all data including Matrix DB)
docker compose down -v
python bridge/auth/setup.py   # re-run setup after volume wipe
```

---

## EC2 deployment

```bash
# On a fresh Ubuntu 22.04 t3.small (2 GB RAM minimum):
curl -O https://raw.githubusercontent.com/codzofrosh/nexa-beeper-connector/main/ec2-setup.sh
bash ec2-setup.sh

# Then follow the printed steps:
# 1. Edit .env  (MATRIX_SERVER_NAME = your EC2 public IP)
# 2. python3 bridge/auth/setup.py
# 3. docker compose pull && docker compose up -d
# 4. Open http://<EC2-IP> in your browser
```

**Security group rules required:** port 22 (SSH), port 80 (HTTP).  
Port 8080 is optional for direct API debugging.

The frontend image (`ghcr.io/codzofrosh/nexa-frontend:latest`) is built and pushed automatically by the [Nexa-FrontEnd](https://github.com/codzofrosh/Nexa-FrontEnd) repo CI on every push to `main`. Make sure the package is set to **public** on GHCR so the EC2 instance can pull it without authentication.

---

## Setting up OAuth

### Google

1. [console.cloud.google.com](https://console.cloud.google.com) → APIs & Services → Credentials
2. Create OAuth 2.0 Client ID (Web application)
3. Add `http://localhost:8080/api/auth/oauth/google/callback` to Authorized redirect URIs
4. Copy Client ID and Client Secret to `.env`

### GitHub

1. GitHub → Settings → Developer settings → OAuth Apps → New OAuth App
2. Set Authorization callback URL to `http://localhost:8080/api/auth/oauth/github/callback`
3. Copy Client ID and Client Secret to `.env`

> For production (EC2), replace `localhost:8080` with your EC2 public IP in the callback URLs and in `OAUTH_REDIRECT_BASE_URL`.
