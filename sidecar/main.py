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
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import uvicorn
import logging
import os
from datetime import datetime, timedelta
# Import unified services
from .database import DatabaseService
from .message_service import (
    MessageClassificationService,
    ActionDecisionService,
    UnifiedMessageService
)
from .auth import hash_password, verify_password, create_session_token

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Nexa Beeper Sidecar", version="1.0.0")
SESSION_COOKIE_NAME = "nexa_session"
SESSION_TTL_HOURS = int(os.getenv("AUTH_SESSION_TTL_HOURS", "24"))

# ============================================
# SERVICE INITIALIZATION
# ============================================

DB_PATH = os.getenv("DB_PATH", "data/nexa.db")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11435")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
USE_OLLAMA = os.getenv("USE_OLLAMA", "true").lower() == "true"
HF_API_KEY = os.getenv("HF_API_KEY")
HF_MODEL = os.getenv("HF_MODEL", "mistralai/Mistral-7B-Instruct-v0.2")

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
    return (datetime.utcnow() + timedelta(hours=SESSION_TTL_HOURS)).isoformat()


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
    .wrap { max-width: 980px; margin: 0 auto; display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 24px; }
    .card { background: #111827; border: 1px solid #334155; border-radius: 16px; padding: 24px; box-shadow: 0 10px 30px rgba(0,0,0,.25); }
    h1, h2 { margin-top: 0; }
    label { display: block; font-size: 14px; margin: 14px 0 6px; color: #cbd5e1; }
    input { width: 100%; box-sizing: border-box; padding: 12px; border-radius: 10px; border: 1px solid #475569; background: #020617; color: #f8fafc; }
    button { margin-top: 16px; width: 100%; padding: 12px; border-radius: 10px; border: none; background: #2563eb; color: white; font-weight: 700; cursor: pointer; }
    button:hover { background: #1d4ed8; }
    .muted { color: #94a3b8; line-height: 1.5; }
    .status { margin-top: 12px; min-height: 20px; color: #7dd3fc; }
    code { background: #020617; padding: 2px 6px; border-radius: 6px; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>Nexa Login</h1>
      <p class="muted">Start with account auth first. Register with your name, email, and password, then log in to create a session cookie for the sidecar.</p>
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
      <p class="muted">This creates the initial user record that we can later tie to mautrix-specific credentials and bridge configuration.</p>
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

@app.get("/", response_class=HTMLResponse)
@app.get("/login", response_class=HTMLResponse)
async def auth_page():
    """Serve the initial login/register page."""
    return HTMLResponse(_auth_page_html())

@app.post("/api/auth/register")
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

@app.post("/api/auth/login")
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

@app.get("/api/auth/me")
async def get_current_user(session_token: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME)):
    """Return the current user associated with the session cookie."""
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = db_service.get_user_by_session(session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    return {"authenticated": True, "user": user}

@app.post("/api/auth/logout")
async def logout_user(response: Response, session_token: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME)):
    """Delete the current session."""
    if session_token:
        db_service.delete_auth_session(session_token)
    response.delete_cookie(SESSION_COOKIE_NAME)
    return {"success": True, "message": "Logged out"}

@app.post("/api/messages/classify", response_model=ActionResponse)
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

@app.post("/api/user/status")
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

@app.get("/api/user/status")
async def get_user_status(user_id: str = "default_user"):
    """Get current user status"""
    status_data = db_service.get_user_status(user_id)
    return {
        "user_id": user_id,
        "status": status_data["status"],
        "auto_reply_message": status_data["auto_reply"]
    }

@app.get("/api/actions/pending")
async def get_pending_actions(limit: int = 50):
    """Get all pending actions"""
    actions = db_service.get_pending_actions(limit=limit)
    return {"actions": actions, "count": len(actions)}

@app.get("/api/messages/recent")
async def get_recent_messages(limit: int = 20):
    """Get recent messages"""
    messages = db_service.get_recent_messages(limit=limit)
    return {"messages": messages, "count": len(messages)}

@app.get("/api/stats")
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

@app.get("/health")
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

if __name__ == "__main__":
    print("\n" + "="*60)
    print("[OK] NEXA BEEPER SIDECAR STARTING")
    print("="*60)
    print(f"Ollama: {'[OK] Available' if classifier_service.ollama_available else '[INFO] Using fallback'}")
    print(f"Model: {OLLAMA_MODEL if classifier_service.ollama_available else 'rule-based'}")
    print(f"Database: {DB_PATH}")
    print("="*60 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
