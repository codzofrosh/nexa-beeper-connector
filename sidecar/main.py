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


# ============================================
# API ENDPOINTS
# ============================================

@app.post("/api/messages/classify", response_model=ActionResponse)
async def classify_message_endpoint(message: IncomingMessage):
    """
    Unified message processing endpoint.
    Combines classification, decision-making, and persistence in one call.
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
        
        if result["status"] == "duplicate":
            logger.warning(f"Duplicate message: {message.id}")
            # Still return 200 but indicate it was a duplicate
            return ActionResponse(
                message_id=message.id,
                action_type=result.get("action", "none"),
                priority="unknown",
                classification={},
                status="duplicate"
            )
        
        return ActionResponse(
            message_id=result["message_id"],
            action_id=result.get("action_id"),
            action_type=result["action_type"],
            priority=result["priority"],
            classification=result["classification"],
            status="pending",
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