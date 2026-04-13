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

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import re
import uvicorn
import logging
import os
# Import unified services
from .database import DatabaseService
from .message_service import (
    MessageClassificationService,
    ActionDecisionService,
    UnifiedMessageService
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Nexa Beeper Sidecar", version="1.0.0")

# ============================================
# SERVICE INITIALIZATION
# ============================================

DB_PATH      = os.getenv("DB_PATH", "data/nexa.db")
OLLAMA_URL   = os.getenv("OLLAMA_URL", "http://localhost:11435")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
USE_OLLAMA   = os.getenv("USE_OLLAMA", "true").lower() == "true"
HF_API_KEY   = os.getenv("HF_API_KEY")
HF_MODEL     = os.getenv("HF_MODEL", "mistralai/Mistral-7B-Instruct-v0.2")

# Matrix / onboarding config
_MATRIX_HOMESERVER  = os.getenv("MATRIX_HOMESERVER", "http://conduit:6167")
_MATRIX_SERVER_NAME = os.getenv("MATRIX_SERVER_NAME", "localhost")
_MATRIX_ADMIN_TOKEN = os.getenv("MATRIX_ACCESS_TOKEN", "")
_BRIDGE_BOT_ID      = os.getenv(
    "WHATSAPP_BRIDGE_BOT",
    f"@whatsappbot:{os.getenv('MATRIX_SERVER_NAME', 'localhost')}",
)

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


# ============================================
# API ENDPOINTS
# ============================================

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

@app.post("/api/messages/incoming")
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


@app.post("/api/bridge/{platform}/login")
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
        bridge_bot_id=req.bridge_bot_id,
    )
    if result["status"] == "error":
        raise HTTPException(status_code=502, detail=result.get("error"))
    return result


@app.get("/api/bridge/{platform}/status")
async def bridge_status(platform: str, bridge_bot_id: Optional[str] = None):
    """Check whether the mautrix bridge is currently connected."""
    manager = _get_auth_manager()
    return await manager.get_status(platform=platform, bridge_bot_id=bridge_bot_id)


@app.post("/api/bridge/{platform}/logout")
async def bridge_logout(platform: str, bridge_bot_id: Optional[str] = None):
    """Disconnect the mautrix bridge for the given platform."""
    manager = _get_auth_manager()
    return await manager.logout(platform=platform, bridge_bot_id=bridge_bot_id)


@app.get("/api/bridge/{platform}/qr")
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
_pending_login_token: dict = {"value": None, "ready": False}


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


@app.get("/api/auth/sso/start")
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


@app.get("/api/auth/sso/callback")
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


@app.get("/api/auth/status")
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


@app.post("/api/onboard/whatsapp/start")
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


@app.get("/api/onboard/whatsapp/qr/{session_id}")
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


@app.get("/api/onboard/whatsapp/status/{session_id}")
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


@app.delete("/api/onboard/whatsapp/session/{session_id}")
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