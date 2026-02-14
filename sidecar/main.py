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
import uvicorn
import logging
import os
import requests
# Import unified services
from .database import DatabaseService
from .message_service import (
    MessageClassificationService,
    ActionDecisionService,
    UnifiedMessageService
)
from .mautrix_service import MautrixBridgeService

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Nexa Beeper Sidecar", version="1.0.0")

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
mautrix_service = MautrixBridgeService(db_service)

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


class MautrixIncomingMessage(BaseModel):
    """Incoming payload shape emitted by mautrix connector integration."""
    message_id: Optional[str] = None
    id: Optional[str] = None
    event_id: Optional[str] = None
    platform: Optional[str] = "whatsapp"
    room_id: Optional[str] = None
    sender: Optional[str] = None
    sender_name: Optional[str] = None
    timestamp: Optional[int] = None
    text: Optional[str] = None
    content: Optional[str] = None
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


class BridgeAction(BaseModel):
    type: str
    should_reply: bool
    reply_text: Optional[str] = None
    notify_user: bool


class IncomingBridgeResponse(BaseModel):
    status: str
    message_id: str
    action: BridgeAction
    priority: str
    classification: Dict[str, Any]

class UserStatus(BaseModel):
    user_id: str = "default_user"
    status: str
    auto_reply_message: Optional[str] = None


class MautrixAuthRequest(BaseModel):
    user_id: str = "default_user"
    base_url: str
    mxid: Optional[str] = None
    password: Optional[str] = None
    access_token: Optional[str] = None
    device_name: str = "nexa-connector"


class MautrixAuthResponse(BaseModel):
    user_id: str
    base_url: str
    matrix_user_id: Optional[str] = None
    device_id: Optional[str] = None
    access_token: str


class IntegrationConnectRequest(BaseModel):
    user_id: str = "default_user"
    app: str
    config: Optional[Dict[str, Any]] = {}


class IntegrationConnectResponse(BaseModel):
    user_id: str
    app: str
    status: str
    config: Dict[str, Any]


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


def _normalize_mautrix_payload(payload: MautrixIncomingMessage) -> IncomingMessage:
    """Map mautrix bridge payloads into the connector's canonical message schema."""
    message_id = payload.message_id or payload.id or payload.event_id
    content = payload.content or payload.text
    sender = payload.sender or payload.sender_name

    if not message_id:
        raise HTTPException(status_code=400, detail="Missing message ID (message_id/id/event_id)")
    if not content:
        raise HTTPException(status_code=400, detail="Missing message content (content/text)")
    if not sender:
        raise HTTPException(status_code=400, detail="Missing sender")

    from time import time
    timestamp = payload.timestamp or int(time())
    # Some Matrix/mautrix timestamps are milliseconds; normalize to unix seconds.
    if timestamp > 10_000_000_000:
        timestamp = timestamp // 1000

    return IncomingMessage(
        id=message_id,
        platform=(payload.platform or "whatsapp").lower(),
        sender=sender,
        content=content,
        timestamp=timestamp,
        room_id=payload.room_id,
        metadata=payload.metadata or {}
    )


def _action_to_bridge_response(result: Dict[str, Any]) -> BridgeAction:
    action_type = result.get("action_type", "none")
    should_reply = action_type == "auto_reply"
    notify_user = action_type in {"notify", "remind"}

    user_status = db_service.get_user_status("default_user")
    auto_reply_message = user_status.get("auto_reply") or "I'm currently unavailable. I'll get back to you soon."

    return BridgeAction(
        type=action_type,
        should_reply=should_reply,
        reply_text=auto_reply_message if should_reply else None,
        notify_user=notify_user,
    )


def _emit_bridge_action(message: IncomingMessage, result: Dict[str, Any], action: BridgeAction) -> None:
    """Best-effort webhook for forwarding action decisions to mautrix-aware workers."""
    callback_url = os.getenv("MAUTRIX_ACTION_WEBHOOK")
    if not callback_url:
        return

    payload = {
        "message_id": result.get("message_id", message.id),
        "room_id": message.room_id,
        "sender": message.sender,
        "platform": message.platform,
        "action": _model_to_dict(action),
        "classification": result.get("classification", {}),
        "priority": result.get("priority", "unknown"),
    }

    try:
        resp = requests.post(callback_url, json=payload, timeout=2)
        if resp.status_code >= 300:
            logger.warning("MAUTRIX_ACTION_WEBHOOK returned %s", resp.status_code)
    except Exception as exc:
        logger.warning("MAUTRIX_ACTION_WEBHOOK unreachable: %s", exc)




def _model_to_dict(model: BaseModel) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()

@app.post("/api/messages/incoming", response_model=IncomingBridgeResponse)
async def process_mautrix_incoming(payload: MautrixIncomingMessage):
    """
    Entry-point for mautrix bridge events.
    Accepts bridge payload shape and routes through the same idempotent classifier pipeline.
    """
    message = _normalize_mautrix_payload(payload)
    result = message_service.process_message(
        message_id=message.id,
        platform=message.platform,
        sender=message.sender,
        content=message.content,
        timestamp=message.timestamp,
        room_id=message.room_id,
    )

    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result.get("error", "Processing failed"))

    if result["status"] == "duplicate":
        action = BridgeAction(type="none", should_reply=False, reply_text=None, notify_user=False)
        return IncomingBridgeResponse(
            status="duplicate",
            message_id=message.id,
            action=action,
            priority="unknown",
            classification={},
        )

    bridge_action = _action_to_bridge_response(result)
    _emit_bridge_action(message, result, bridge_action)

    return IncomingBridgeResponse(
        status="success",
        message_id=result["message_id"],
        action=bridge_action,
        priority=result["priority"],
        classification=result["classification"],
    )



@app.post("/api/mautrix/auth", response_model=MautrixAuthResponse)
async def mautrix_authenticate(request: MautrixAuthRequest):
    """Authenticate against mautrix/Matrix and persist access token for connector usage."""
    try:
        result = mautrix_service.authenticate(
            user_id=request.user_id,
            base_url=request.base_url,
            mxid=request.mxid,
            password=request.password,
            access_token=request.access_token,
            device_name=request.device_name,
        )
        return MautrixAuthResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Mautrix authentication failed: %s", e, exc_info=True)
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/api/mautrix/integrations/connect", response_model=IntegrationConnectResponse)
async def connect_mautrix_integration(request: IntegrationConnectRequest):
    """Register a mautrix-backed app integration (whatsapp now, extensible to more apps)."""
    try:
        result = mautrix_service.connect_integration(
            user_id=request.user_id,
            app=request.app,
            config=request.config or {},
        )
        return IntegrationConnectResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Integration connect failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/mautrix/integrations")
async def list_mautrix_integrations(user_id: str = "default_user"):
    """List currently connected mautrix-backed apps for a connector user."""
    return {"user_id": user_id, "integrations": mautrix_service.list_integrations(user_id)}

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
