# sidecar/main.py
"""
Nexa Sidecar API - Unified Message Classification and Action Service

This module integrates:
- Message classification (via multiple LLM backends)
- Database persistence (with idempotency)
- Action decision making
- Status tracking

All combined into a single unified service pipeline.
"""

from fastapi import FastAPI, HTTPException, Response, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import re
import uvicorn
import logging
import os
from datetime import datetime, timedelta, timezone
# Import unified services
from .database import DatabaseService
from .message_service import (
    MessageClassificationService,
    UnifiedMessageService
)
from .auth import hash_password, verify_password, create_session_token
from . import oauth as _oauth
from .dev_guide import render as _dev_guide_html

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Nexa Sidecar API",
    version="1.0.0",
    description=(
        "AI message classification and bridge management for WhatsApp and LinkedIn via Matrix.\n\n"
        "**Auth:** Most endpoints are unauthenticated (the sidecar runs in a trusted internal network). "
        "User-facing auth endpoints set an `HttpOnly` session cookie (`nexa_session`). "
        "Include `credentials: 'include'` in all `fetch()` calls from a browser.\n\n"
        "**Base URL:** `http://localhost:8080` in local dev, or the value of `SIDECAR_URL` in production.\n\n"
        "**Interactive guide:** `GET /dev` — full frontend integration guide with code examples."
    ),
    openapi_tags=[
        {"name": "auth",       "description": "Register, login, logout, OAuth (Google / GitHub)"},
        {"name": "onboarding", "description": "WhatsApp QR-code onboarding flow"},
        {"name": "bridge",     "description": "Connect / disconnect WhatsApp and LinkedIn bridges"},
        {"name": "messages",   "description": "Classify incoming messages and retrieve history"},
        {"name": "user",       "description": "User availability status and pending actions"},
        {"name": "system",     "description": "Health check and statistics"},
    ],
)
_ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost,http://localhost:3000,http://localhost:5173").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,   # needed for session cookie
    allow_methods=["*"],
    allow_headers=["*"],
)

SESSION_COOKIE_NAME = "nexa_session"
SESSION_TTL_HOURS = int(os.getenv("AUTH_SESSION_TTL_HOURS", "24"))

# ============================================
# SERVICE INITIALIZATION
# ============================================

DB_PATH      = os.getenv("DB_PATH", "data/nexa.db")
OLLAMA_URL   = os.getenv("OLLAMA_URL", "http://localhost:11435")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
USE_OLLAMA   = os.getenv("USE_OLLAMA", "true").lower() == "true"
HF_API_KEY   = os.getenv("HF_API_KEY")
HF_MODEL     = os.getenv("HF_MODEL", "mistralai/Mistral-7B-Instruct-v0.2")

# OAuth config
_OAUTH_REDIRECT_BASE = os.getenv("OAUTH_REDIRECT_BASE_URL", "http://localhost:8080")

# Matrix / onboarding config
_MATRIX_HOMESERVER  = os.getenv("MATRIX_HOMESERVER", "http://conduit:6167")
_MATRIX_SERVER_NAME = os.getenv("MATRIX_SERVER_NAME", "localhost")
_MATRIX_ADMIN_TOKEN = os.getenv("MATRIX_ACCESS_TOKEN", "")
_BRIDGE_BOT_ID      = os.getenv(
    "WHATSAPP_BRIDGE_BOT",
    f"@whatsappbot:{os.getenv('MATRIX_SERVER_NAME', 'localhost')}",
)

# Platform → bridge bot Matrix ID (env vars take priority over defaults)
_PLATFORM_BOT_IDS: dict = {
    "whatsapp": os.getenv("WHATSAPP_BRIDGE_BOT", f"@whatsappbot:{_MATRIX_SERVER_NAME}"),
    "linkedin": os.getenv("LINKEDIN_BRIDGE_BOT", f"@linkedinbot:{_MATRIX_SERVER_NAME}"),
}


def _resolve_bridge_bot(platform: str, override: Optional[str] = None) -> Optional[str]:
    """Return the bridge bot Matrix ID for a platform, respecting env var overrides."""
    return override or _PLATFORM_BOT_IDS.get(platform)

# Initialize services
db_service = DatabaseService(db_path=DB_PATH)
classifier_service = MessageClassificationService(
    ollama_url=OLLAMA_URL,
    ollama_model=OLLAMA_MODEL,
    use_ollama=USE_OLLAMA,
    hf_api_key=HF_API_KEY,
    hf_model=HF_MODEL
)
message_service = UnifiedMessageService(db_service, classifier_service)

logger.info(f"Services initialized: DB={DB_PATH}, Ollama={classifier_service.ollama_available}")

# Onboarding service — lazy-initialised on first request
_onboarding_service = None

def _get_onboarding_service():
    global _onboarding_service
    if _onboarding_service is None:
        from sidecar.onboarding import OnboardingService
        _onboarding_service = OnboardingService(
            homeserver=_MATRIX_HOMESERVER,
            server_name=_MATRIX_SERVER_NAME,
            admin_token=_MATRIX_ADMIN_TOKEN,
            bridge_bot_id=_BRIDGE_BOT_ID,
        )
    return _onboarding_service


# ============================================
# PYDANTIC MODELS
# ============================================

class IncomingMessage(BaseModel):
    id: str
    platform: str
    sender: str
    content: str
    timestamp: int
    room_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = {}

class Classification(BaseModel):
    priority: str
    category: str
    requires_action: bool
    confidence: float
    reasoning: str
    classifier_used: str

class ActionResponse(BaseModel):
    message_id: str
    action_id: Optional[int] = None
    action_type: str
    priority: str
    classification: Dict[str, Any]
    status: str
    user_status: Optional[str] = None

class UserStatus(BaseModel):
    user_id: str = "default_user"
    status: str
    auto_reply_message: Optional[str] = None

class RegisterUserRequest(BaseModel):
    name: str
    email: str
    password: str

class LoginUserRequest(BaseModel):
    email: str
    password: str


def _session_expiry() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)).isoformat()


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=SESSION_TTL_HOURS * 3600,
    )


def _auth_page_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Nexa Auth</title>
  <style>
    body { font-family: Arial, sans-serif; background: #0f172a; color: #e2e8f0; margin: 0; padding: 32px; }
    .outer { max-width: 980px; margin: 0 auto; }
    .oauth-section { margin-bottom: 28px; }
    .oauth-section h2 { margin: 0 0 16px; font-size: 18px; color: #94a3b8; font-weight: 500; text-align: center; }
    .oauth-buttons { display: flex; gap: 12px; flex-wrap: wrap; justify-content: center; }
    .btn-oauth { display: flex; align-items: center; gap: 10px; padding: 12px 24px; border-radius: 10px;
                 border: 1px solid #334155; background: #111827; color: #e2e8f0; font-size: 15px;
                 font-weight: 600; cursor: pointer; text-decoration: none; transition: background .15s; }
    .btn-oauth:hover { background: #1e293b; }
    .btn-oauth svg { flex-shrink: 0; }
    .divider { display: flex; align-items: center; gap: 12px; margin: 8px 0 28px; color: #475569; font-size: 13px; }
    .divider::before, .divider::after { content: ""; flex: 1; height: 1px; background: #1e293b; }
    .wrap { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 24px; }
    .card { background: #111827; border: 1px solid #334155; border-radius: 16px; padding: 24px; box-shadow: 0 10px 30px rgba(0,0,0,.25); }
    h1, h2 { margin-top: 0; }
    label { display: block; font-size: 14px; margin: 14px 0 6px; color: #cbd5e1; }
    input { width: 100%; box-sizing: border-box; padding: 12px; border-radius: 10px; border: 1px solid #475569; background: #020617; color: #f8fafc; }
    button[type=submit] { margin-top: 16px; width: 100%; padding: 12px; border-radius: 10px; border: none; background: #2563eb; color: white; font-weight: 700; cursor: pointer; }
    button[type=submit]:hover { background: #1d4ed8; }
    .muted { color: #94a3b8; line-height: 1.5; }
    .status { margin-top: 12px; min-height: 20px; color: #7dd3fc; }
    code { background: #020617; padding: 2px 6px; border-radius: 6px; }
  </style>
</head>
<body>
  <div class="outer">
    <div class="oauth-section">
      <h2>Sign in with</h2>
      <div class="oauth-buttons">
        <a class="btn-oauth" href="/api/auth/oauth/google/start">
          <svg width="20" height="20" viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/><path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.18 1.48-4.97 2.29-8.16 2.29-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg>
          Continue with Google
        </a>
        <a class="btn-oauth" href="/api/auth/oauth/github/start">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="#e2e8f0"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.44 9.8 8.21 11.39.6.11.82-.26.82-.58v-2.03c-3.34.72-4.04-1.61-4.04-1.61-.55-1.39-1.34-1.76-1.34-1.76-1.09-.75.08-.73.08-.73 1.2.08 1.84 1.24 1.84 1.24 1.07 1.83 2.81 1.3 3.5.99.11-.78.42-1.3.76-1.6-2.67-.3-5.47-1.33-5.47-5.93 0-1.31.47-2.38 1.24-3.22-.13-.3-.54-1.52.12-3.17 0 0 1.01-.32 3.3 1.23a11.5 11.5 0 013-.4c1.02 0 2.04.14 3 .4 2.28-1.55 3.29-1.23 3.29-1.23.66 1.65.25 2.87.12 3.17.77.84 1.24 1.91 1.24 3.22 0 4.61-2.81 5.63-5.48 5.92.43.37.81 1.1.81 2.22v3.29c0 .32.22.7.83.58C20.56 21.8 24 17.3 24 12c0-6.63-5.37-12-12-12z"/></svg>
          Continue with GitHub
        </a>
      </div>
    </div>
    <div class="divider">or use email &amp; password</div>
    <div class="wrap">
      <div class="card">
        <h1>Log in</h1>
        <p class="muted">Enter your email and password to create a session cookie for the sidecar.</p>
        <form id="login-form">
          <label for="login-email">Email</label>
          <input id="login-email" name="email" type="email" placeholder="you@example.com" required />
          <label for="login-password">Password</label>
          <input id="login-password" name="password" type="password" placeholder="••••••••" required />
          <button type="submit">Log in</button>
        </form>
        <div id="login-status" class="status"></div>
      </div>
      <div class="card">
        <h2>Create account</h2>
        <p class="muted">Register with email and password. You can also sign in with Google or GitHub above.</p>
        <form id="register-form">
          <label for="register-name">Name</label>
          <input id="register-name" name="name" type="text" placeholder="Jane Doe" required />
          <label for="register-email">Email</label>
          <input id="register-email" name="email" type="email" placeholder="jane@example.com" required />
          <label for="register-password">Password</label>
          <input id="register-password" name="password" type="password" placeholder="Choose a strong password" required />
          <button type="submit">Create account</button>
        </form>
        <div id="register-status" class="status"></div>
      </div>
    </div>
  </div>
  <script>
    async function submitJson(formId, url, statusId) {
      const form = document.getElementById(formId);
      const status = document.getElementById(statusId);
      form.addEventListener('submit', async (event) => {
        event.preventDefault();
        status.textContent = 'Submitting...';
        const payload = Object.fromEntries(new FormData(form).entries());
        const response = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (!response.ok) {
          status.textContent = data.detail || 'Request failed';
          status.style.color = '#fda4af';
          return;
        }
        status.textContent = JSON.stringify(data);
        status.style.color = '#86efac';
      });
    }
    submitJson('login-form', '/api/auth/login', 'login-status');
    submitJson('register-form', '/api/auth/register', 'register-status');
  </script>
</body>
</html>"""


# ============================================
# API ENDPOINTS
# ============================================

@app.get("/dev", response_class=HTMLResponse, include_in_schema=False)
async def dev_guide():
    """Frontend developer integration guide with all endpoints, examples, and a copy-paste JS client."""
    return HTMLResponse(_dev_guide_html())


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
@app.get("/login", response_class=HTMLResponse, include_in_schema=False)
async def auth_page():
    """Serve the initial login/register page."""
    return HTMLResponse(_auth_page_html())

@app.post("/api/auth/register", tags=["auth"])
async def register_user(payload: RegisterUserRequest, response: Response):
    """Create a sidecar user account and login session."""
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long")

    created_user = db_service.create_user(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
    )
    if not created_user:
        raise HTTPException(status_code=409, detail="An account with that email already exists")

    token = create_session_token()
    if not db_service.create_auth_session(created_user["id"], token, _session_expiry()):
        raise HTTPException(status_code=500, detail="Failed to create auth session")

    _set_session_cookie(response, token)
    return {
        "success": True,
        "user": created_user,
        "message": "Account created",
    }

@app.post("/api/auth/login", tags=["auth"])
async def login_user(payload: LoginUserRequest, response: Response):
    """Authenticate an existing user with email/password."""
    user = db_service.get_user_by_email(payload.email)
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_session_token()
    if not db_service.create_auth_session(user["id"], token, _session_expiry()):
        raise HTTPException(status_code=500, detail="Failed to create auth session")

    _set_session_cookie(response, token)
    return {
        "success": True,
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
        },
        "message": "Logged in",
    }

@app.get("/api/auth/me", tags=["auth"])
async def get_current_user(session_token: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME)):
    """Return the current user associated with the session cookie."""
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = db_service.get_user_by_session(session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    return {"authenticated": True, "user": user}

@app.post("/api/auth/logout", tags=["auth"])
async def logout_user(response: Response, session_token: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME)):
    """Delete the current session."""
    if session_token:
        db_service.delete_auth_session(session_token)
    response.delete_cookie(SESSION_COOKIE_NAME)
    return {"success": True, "message": "Logged out"}

@app.get("/api/auth/oauth/{provider}/start", tags=["auth"])
async def oauth_start(provider: str):
    """Redirect the browser to the OAuth provider's consent screen."""
    if provider == "google":
        if not _oauth.google_configured():
            raise HTTPException(status_code=503, detail="Google OAuth is not configured (GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET missing)")
        redirect_uri = f"{_OAUTH_REDIRECT_BASE}/api/auth/oauth/google/callback"
        state = _oauth.generate_state("google")
        url = _oauth.google_auth_url(redirect_uri, state)
    elif provider == "github":
        if not _oauth.github_configured():
            raise HTTPException(status_code=503, detail="GitHub OAuth is not configured (GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET missing)")
        redirect_uri = f"{_OAUTH_REDIRECT_BASE}/api/auth/oauth/github/callback"
        state = _oauth.generate_state("github")
        url = _oauth.github_auth_url(redirect_uri, state)
    else:
        raise HTTPException(status_code=404, detail=f"Unknown OAuth provider: {provider!r}")
    return RedirectResponse(url)


@app.get("/api/auth/oauth/{provider}/callback", tags=["auth"], include_in_schema=False)
async def oauth_callback(provider: str, code: str = "", state: str = "", error: str = ""):
    """
    Receive the redirect from the OAuth provider.
    Exchange the code for user info, upsert the user, set a session cookie.
    """
    if error:
        raise HTTPException(status_code=400, detail=f"OAuth error from {provider}: {error}")

    if not _oauth.consume_state(state):
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state — possible CSRF attempt")

    try:
        if provider == "google":
            redirect_uri = f"{_OAUTH_REDIRECT_BASE}/api/auth/oauth/google/callback"
            user_info = await _oauth.exchange_google_code(code, redirect_uri)
        elif provider == "github":
            redirect_uri = f"{_OAUTH_REDIRECT_BASE}/api/auth/oauth/github/callback"
            user_info = await _oauth.exchange_github_code(code, redirect_uri)
        else:
            raise HTTPException(status_code=404, detail=f"Unknown OAuth provider: {provider!r}")
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    user = db_service.upsert_oauth_user(
        name=user_info["name"],
        email=user_info["email"],
        provider=provider,
        sub=user_info["sub"],
    )
    if not user:
        raise HTTPException(status_code=500, detail="Failed to upsert OAuth user")

    token = create_session_token()
    if not db_service.create_auth_session(user["id"], token, _session_expiry()):
        raise HTTPException(status_code=500, detail="Failed to create auth session")

    resp = RedirectResponse(url="/", status_code=302)
    _set_session_cookie(resp, token)
    return resp


@app.post("/api/messages/classify", response_model=ActionResponse, tags=["messages"])
async def classify_message_endpoint(message: IncomingMessage):
    """
    Unified message processing endpoint.
    Idempotent: NEW messages get classification, DUPLICATES get only metadata.
    """
    try:
        result = message_service.process_message(
            message_id=message.id,
            platform=message.platform,
            sender=message.sender,
            content=message.content,
            timestamp=message.timestamp,
            room_id=message.room_id
        )
        
        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result.get("error", "Processing failed"))
        
        # DUPLICATE: Return metadata only, NO classification
        if result["status"] == "duplicate":
            logger.warning(f"Duplicate message: {message.id}")
            return ActionResponse(
                message_id=message.id,
                action_type="none",
                priority="unknown",
                classification={},  # Empty - no classification for duplicates
                status="duplicate",
                user_status=None
            )
        
        # SUCCESS: Return full classification and action
        return ActionResponse(
            message_id=result["message_id"],
            action_id=result.get("action_id"),
            action_type=result["action_type"],
            priority=result["priority"],
            classification=result["classification"],
            status="success",
            user_status=result.get("user_status")
        )
        
    except Exception as e:
        logger.error(f"Endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/user/status", tags=["user"])
async def update_user_status(status: UserStatus):
    """Update user status (available/busy/dnd)"""
    success = db_service.update_user_status(
        user_id=status.user_id,
        status=status.status,
        auto_reply=status.auto_reply_message
    )
    
    if success:
        logger.info(f"User status updated to: {status.status}")
        return {"success": True, "status": status.status}
    else:
        raise HTTPException(status_code=500, detail="Failed to update user status")

@app.get("/api/user/status", tags=["user"])
async def get_user_status(user_id: str = "default_user"):
    """Get current user status"""
    status_data = db_service.get_user_status(user_id)
    return {
        "user_id": user_id,
        "status": status_data["status"],
        "auto_reply_message": status_data["auto_reply"]
    }

@app.get("/api/actions/pending", tags=["user"])
async def get_pending_actions(limit: int = 50):
    """Get all pending actions"""
    actions = db_service.get_pending_actions(limit=limit)
    return {"actions": actions, "count": len(actions)}

@app.get("/api/messages/recent", tags=["messages"])
async def get_recent_messages(limit: int = 20):
    """Get recent messages"""
    messages = db_service.get_recent_messages(limit=limit)
    return {"messages": messages, "count": len(messages)}

@app.get("/api/stats", tags=["system"])
async def get_stats():
    """Get system statistics"""
    stats = db_service.get_statistics()
    return {
        "total_messages": stats["total_messages"],
        "pending_actions": stats["pending_actions"],
        "priority_breakdown": stats["priority_breakdown"],
        "classifier_breakdown": stats["classifier_breakdown"],
        "ollama_enabled": classifier_service.ollama_available,
        "ollama_model": OLLAMA_MODEL if classifier_service.ollama_available else None,
        "classifier": "ollama" if classifier_service.ollama_available else "huggingface" if HF_API_KEY else "rule-based"
    }

@app.get("/health", tags=["system"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "nexa-sidecar",
        "ollama_available": classifier_service.ollama_available,
        "ollama_model": OLLAMA_MODEL if classifier_service.ollama_available else None,
        "hf_available": HF_API_KEY is not None,
        "db_path": DB_PATH
    }


# ============================================
# MAUTRIX WEBHOOK — incoming messages from bridge
# ============================================

class MatrixWebhookEvent(BaseModel):
    """Raw Matrix event forwarded by the mautrix bridge (or WhatsAppConnector)."""
    event_id: str
    room_id: str
    sender: str
    content: Dict[str, Any]
    origin_server_ts: int
    platform: Optional[str] = "whatsapp"

@app.post("/api/messages/incoming", tags=["messages"])
async def incoming_message(event: MatrixWebhookEvent):
    """
    Receives raw Matrix events from the mautrix-whatsapp bridge webhook.

    The bridge posts here when a WhatsApp message arrives.
    We extract the text body, run the classify pipeline, and store the result.
    """
    body = event.content.get("body", "").strip()
    msgtype = event.content.get("msgtype", "")

    # Only process text messages
    if msgtype != "m.text" or not body:
        return {"status": "ignored", "reason": "non-text event"}

    try:
        result = message_service.process_message(
            message_id=event.event_id,
            platform=event.platform,
            sender=event.sender,
            content=body,
            timestamp=event.origin_server_ts,
            room_id=event.room_id,
        )
        logger.info(
            "Incoming webhook: %s from %s [%s]",
            event.event_id, event.sender, result.get("action_type", "?"),
        )
        return {"status": result.get("status", "ok"), "action_type": result.get("action_type")}
    except Exception as exc:
        logger.error("Webhook processing error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ============================================
# BRIDGE AUTH ENDPOINTS
# ============================================

# Lazy singleton — created on first request so startup is not blocked
_auth_manager = None

def _get_auth_manager():
    global _auth_manager
    if _auth_manager is None:
        homeserver   = os.getenv("MATRIX_HOMESERVER", "")
        user_id      = os.getenv("MATRIX_USER", "")
        access_token = os.getenv("MATRIX_ACCESS_TOKEN", "")
        if not all([homeserver, user_id, access_token]):
            raise HTTPException(
                status_code=500,
                detail="Matrix credentials not configured. Set MATRIX_HOMESERVER, MATRIX_USER, MATRIX_ACCESS_TOKEN in .env",
            )
        from bridge.auth.manager import BridgeAuthManager
        _auth_manager = BridgeAuthManager(
            homeserver=homeserver,
            user_id=user_id,
            access_token=access_token,
        )
    return _auth_manager


class BridgeLoginRequest(BaseModel):
    platform: str = "whatsapp"
    bridge_bot_id: Optional[str] = None  # overrides the default for the platform


@app.post("/api/bridge/{platform}/login", tags=["bridge"])
async def bridge_login(platform: str, req: BridgeLoginRequest):
    """
    Initiate authentication for a mautrix bridge.

    Sends the 'login' command to the bridge bot and waits up to 30 s for a
    QR code. Returns the QR as a base64 data-URI PNG (or raw text for older
    bridge versions).

    The caller should display the QR code to the user, who then scans it with
    the platform app (WhatsApp, Telegram, etc.).
    """
    manager = _get_auth_manager()
    result = await manager.start_login(
        platform=platform,
        bridge_bot_id=_resolve_bridge_bot(platform, req.bridge_bot_id),
    )
    if result["status"] == "error":
        raise HTTPException(status_code=502, detail=result.get("error"))
    return result


@app.get("/api/bridge/{platform}/status", tags=["bridge"])
async def bridge_status(platform: str, bridge_bot_id: Optional[str] = None):
    """Check whether the mautrix bridge is currently connected."""
    manager = _get_auth_manager()
    return await manager.get_status(
        platform=platform,
        bridge_bot_id=_resolve_bridge_bot(platform, bridge_bot_id),
    )


@app.post("/api/bridge/{platform}/logout", tags=["bridge"])
async def bridge_logout(platform: str, bridge_bot_id: Optional[str] = None):
    """Disconnect the mautrix bridge for the given platform."""
    manager = _get_auth_manager()
    return await manager.logout(
        platform=platform,
        bridge_bot_id=_resolve_bridge_bot(platform, bridge_bot_id),
    )


@app.get("/api/bridge/{platform}/qr", tags=["bridge"])
async def bridge_qr(platform: str):
    """
    Return the most recently received QR code for the platform (if any).

    Useful for polling: call /login first, then poll /qr until it returns data,
    then display it to the user.
    """
    manager = _get_auth_manager()
    return {
        "platform": platform,
        "qr": manager._qr_data,
        "status": manager._conn_status,
    }


# ============================================
# MATRIX SSO AUTH ENDPOINTS
# ============================================

# Sidecar public URL (used for SSO callback)
_SIDECAR_URL      = os.getenv("SIDECAR_URL", "http://localhost:8080").rstrip("/")
_SSO_CALLBACK_URL = f"{_SIDECAR_URL}/api/auth/sso/callback"

# Holds the pending loginToken between the /start and /callback calls
_pending_login_token: Dict[str, Any] = {"value": None, "ready": False}


def _sso_redirect_url(homeserver: str, callback_url: str) -> str:
    from urllib.parse import quote
    return f"{homeserver}/_matrix/client/v3/login/sso/redirect?redirectUrl={quote(callback_url, safe='')}"


async def _exchange_login_token(homeserver: str, login_token: str) -> dict:
    import aiohttp as _aiohttp
    async with _aiohttp.ClientSession() as session:
        async with session.post(
            f"{homeserver}/_matrix/client/v3/login",
            json={"type": "m.login.token", "token": login_token},
        ) as resp:
            data = await resp.json()
            if resp.status != 200:
                raise HTTPException(
                    status_code=502,
                    detail=f"Token exchange failed: {data.get('error', data)}",
                )
            return data


def _write_token_to_env(access_token: str) -> None:
    """Overwrite MATRIX_ACCESS_TOKEN in the .env file."""
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if not os.path.exists(env_path):
        return
    text = open(env_path).read()
    line = f"MATRIX_ACCESS_TOKEN={access_token}"
    new_text, n = re.subn(r"^MATRIX_ACCESS_TOKEN\s*=.*$", line, text, flags=re.MULTILINE)
    if n == 0:
        new_text = text.rstrip("\n") + f"\n{line}\n"
    open(env_path, "w").write(new_text)


@app.get("/api/auth/sso/start", tags=["auth"], include_in_schema=False)
async def sso_start():
    """
    Step 1 — Returns the Beeper SSO login URL.

    Open this URL in a browser. After Google/Apple login, Beeper will
    redirect to /api/auth/sso/callback and the token is stored automatically.
    """
    sso_url = _sso_redirect_url(_MATRIX_HOMESERVER, _SSO_CALLBACK_URL)
    return {
        "sso_url": sso_url,
        "callback_url": _SSO_CALLBACK_URL,
        "instructions": "Open sso_url in a browser, log in with Google/Apple, then call /api/auth/status to verify.",
    }


@app.get("/api/auth/sso/callback", tags=["auth"], include_in_schema=False)
async def sso_callback(loginToken: str):
    """
    Step 2 — Receives the loginToken from Beeper after SSO redirect.

    Beeper calls this automatically after the user logs in. It exchanges
    the short-lived loginToken for a permanent access_token and saves it to .env.
    """
    result = await _exchange_login_token(_MATRIX_HOMESERVER, loginToken)

    access_token = result.get("access_token", "")
    user_id      = result.get("user_id", "")

    if not access_token:
        raise HTTPException(status_code=502, detail="No access_token in response")

    # Persist to .env and update running environment
    _write_token_to_env(access_token)
    os.environ["MATRIX_ACCESS_TOKEN"] = access_token

    # Reset cached auth manager so it picks up the new token next call
    global _auth_manager
    if _auth_manager is not None:
        await _auth_manager.close()
        _auth_manager = None

    logger.info("SSO login successful for %s", user_id)

    # Return a friendly HTML page so the browser tab shows success
    from fastapi.responses import HTMLResponse
    return HTMLResponse(
        content=(
            "<html><body style='font-family:sans-serif;padding:40px;max-width:500px'>"
            f"<h2>✅ Logged in as {user_id}</h2>"
            "<p>Access token saved. You can close this tab.</p>"
            "<p><strong>Next step:</strong> WhatsApp bridge login is now ready.<br>"
            "Call <code>POST /api/bridge/whatsapp/login</code> or run "
            "<code>python bridge/auth/whatsapp_login.py</code></p>"
            "</body></html>"
        )
    )


@app.get("/api/auth/status", tags=["auth"])
async def auth_status():
    """
    Check whether the current MATRIX_ACCESS_TOKEN is valid by calling
    the homeserver's /whoami endpoint.
    """
    import aiohttp as _aiohttp
    token = os.getenv("MATRIX_ACCESS_TOKEN", "")
    if not token:
        return {"authenticated": False, "reason": "No token in environment"}

    try:
        async with _aiohttp.ClientSession() as session:
            async with session.get(
                f"{_MATRIX_HOMESERVER}/_matrix/client/v3/account/whoami",
                headers={"Authorization": f"Bearer {token}"},
            ) as resp:
                data = await resp.json()
                if resp.status == 200:
                    return {"authenticated": True, "user_id": data.get("user_id"), "device_id": data.get("device_id")}
                return {"authenticated": False, "reason": data.get("error", str(data))}
    except Exception as exc:
        return {"authenticated": False, "reason": str(exc)}


# ============================================
# USER ONBOARDING ENDPOINTS
# ============================================
#
# These are the ONLY endpoints end-users interact with.
# All Matrix / bridge complexity is handled server-side.
#
# Typical client flow:
#   1. POST /api/onboard/whatsapp/start          → get session_id + QR
#   2. Display QR code to user
#   3. GET  /api/onboard/whatsapp/status/{id}    → poll every 3s until "connected"
#   4. GET  /api/onboard/whatsapp/qr/{id}        → refresh QR every 18s
#   5. DELETE /api/onboard/whatsapp/session/{id} → cleanup on cancel/timeout


class OnboardStartRequest(BaseModel):
    user_id: str   # your app's user identifier (email, UUID, etc.)


@app.post("/api/onboard/whatsapp/start", tags=["onboarding"])
async def onboard_start(req: OnboardStartRequest):
    """
    Begin WhatsApp onboarding for a user.

    Creates a Matrix account for the user, DMs the WhatsApp bridge bot,
    waits up to 30 s for the first QR code, and returns it as a base64
    PNG data-URI.

    The client should display the QR code immediately. The user scans it
    with WhatsApp on their phone. Call /status to know when they've done so.
    """
    svc = _get_onboarding_service()
    result = await svc.start_session(req.user_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail=result.get("error"))
    return result


@app.get("/api/onboard/whatsapp/qr/{session_id}", tags=["onboarding"])
async def onboard_qr(session_id: str):
    """
    Return the latest QR code for an active onboarding session.

    mautrix-whatsapp refreshes the QR every ~20 seconds. Clients should
    call this endpoint every 18 seconds and re-render the QR image so
    the user can scan a fresh code. A stale QR will not work.
    """
    svc = _get_onboarding_service()
    result = await svc.get_qr(session_id)
    if result["status"] == "not_found":
        raise HTTPException(status_code=404, detail="Session not found")
    return result


@app.get("/api/onboard/whatsapp/status/{session_id}", tags=["onboarding"])
async def onboard_status(session_id: str):
    """
    Poll WhatsApp connection status for an onboarding session.

    Call every 3 seconds after showing the QR code.

    Possible status values:
      pending_qr  — waiting for user to scan
      connected   — WhatsApp authenticated, messages will start flowing
      expired     — 5-minute TTL exceeded, start a new session
      not_found   — unknown session_id
    """
    svc = _get_onboarding_service()
    result = await svc.get_status(session_id)
    if result["status"] == "not_found":
        raise HTTPException(status_code=404, detail="Session not found")
    return result


@app.delete("/api/onboard/whatsapp/session/{session_id}", tags=["onboarding"])
async def onboard_cancel(session_id: str):
    """
    Cancel and clean up an onboarding session.

    Call this if the user closes the QR screen, navigates away, or after
    a "connected" confirmation to release the Matrix client resources.
    """
    svc = _get_onboarding_service()
    await svc.cleanup_session(session_id)
    return {"status": "cleaned_up", "session_id": session_id}


if __name__ == "__main__":
    print("\n" + "="*60)
    print("[OK] NEXA BEEPER SIDECAR STARTING")
    print("="*60)
    print(f"Ollama: {'[OK] Available' if classifier_service.ollama_available else '[INFO] Using fallback'}")
    print(f"Model: {OLLAMA_MODEL if classifier_service.ollama_available else 'rule-based'}")
    print(f"Database: {DB_PATH}")
    print("="*60 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
