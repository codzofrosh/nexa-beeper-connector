# sidecar/main.py
"""
Nexa Sidecar API - Message classification and action decision service
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import uvicorn
import logging
from datetime import datetime
import sqlite3
import json
import requests
import os

app = FastAPI(title="Nexa Beeper Sidecar", version="1.0.0")
# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = FastAPI(title="Nexa Beeper Sidecar", version="1.0.0")
# ============================================
# Database setup (keep same as before)
DB_PATH = os.getenv("DB_PATH", "data/nexa.db")
def init_db():
    """Initialize SQLite database"""
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            platform TEXT NOT NULL,
            sender TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp INTEGER NOT NULL,
            classification TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT NOT NULL,
            action_type TEXT NOT NULL,
            priority TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            action_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            executed_at TIMESTAMP,
            FOREIGN KEY (message_id) REFERENCES messages(id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_status (
            user_id TEXT PRIMARY KEY,
            status TEXT DEFAULT 'available',
            auto_reply_message TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()
    logger.info("✅ Database initialized")

init_db()

# ============================================
# OPEN-SOURCE LLM INTEGRATION
# ============================================

# Configuration
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11435")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
USE_OLLAMA = os.getenv("USE_OLLAMA", "true").lower() == "true"

# Alternative: Hugging Face Inference API (also free)
HF_API_URL = os.getenv("HF_API_URL", "https://api-inference.huggingface.co/models/")
HF_MODEL = os.getenv("HF_MODEL", "mistralai/Mistral-7B-Instruct-v0.2")
HF_API_KEY = os.getenv("HF_API_KEY")  # Free tier available

def test_ollama_connection():
    """Test if Ollama is available"""
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=2)
        if response.status_code == 200:
            models = [model['name'] for model in response.json().get('models', [])]
            logger.info(f"✅ Ollama connected. Available models: {models}")
            return True
    except Exception as e:
        logger.warning(f"⚠️  Ollama not available: {e}")
    return False

# Check Ollama availability at startup
OLLAMA_AVAILABLE = test_ollama_connection() if USE_OLLAMA else False

# Pydantic models
class IncomingMessage(BaseModel):
    id: str
    platform: str
    sender: str
    content: str
    timestamp: int
    metadata: Optional[Dict[str, Any]] = {}

class Classification(BaseModel):
    priority: str
    category: str
    requires_action: bool
    confidence: float
    reasoning: str

class ActionResponse(BaseModel):
    message_id: str
    action_type: str
    priority: str
    classification: Classification
    status: str

class UserStatus(BaseModel):
    user_id: str = "default_user"
    status: str
    auto_reply_message: Optional[str] = None

# ============================================
# CLASSIFICATION FUNCTIONS
# ============================================

def classify_with_ollama(message: str) -> Classification:
    """Use Ollama (local LLM) to classify message"""
    try:
        prompt = f"""Analyze this message and classify its priority.

Message: "{message}"

Respond with ONLY valid JSON in this exact format:
{{
    "priority": "urgent|high|normal|low",
    "category": "work|personal|social|marketing",
    "requires_action": true or false,
    "confidence": 0.0 to 1.0,
    "reasoning": "brief explanation"
}}

Rules:
- "urgent": emergencies, system down, critical issues
- "high": important deadlines, meetings, client requests
- "normal": regular questions, general communication
- "low": casual chat, acknowledgments

JSON response:"""

        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "format": "json"  # Force JSON output
            },
            timeout=10
        )
        
        if response.status_code != 200:
            raise Exception(f"Ollama error: {response.text}")
        
        result_text = response.json()['response']
        
        # Parse JSON
        result_text = result_text.strip()
        if "```json" in result_text:
            start = result_text.find("```json") + 7
            end = result_text.find("```", start)
            result_text = result_text[start:end].strip()
        elif "```" in result_text:
            start = result_text.find("```") + 3
            end = result_text.find("```", start)
            result_text = result_text[start:end].strip()
        
        result = json.loads(result_text)
        
        return Classification(
            priority=result.get('priority', 'normal'),
            category=result.get('category', 'personal'),
            requires_action=result.get('requires_action', False),
            confidence=result.get('confidence', 0.7),
            reasoning=result.get('reasoning', 'Ollama classification')
        )
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}. Response: {result_text[:200]}")
        return classify_fallback(message)
    except Exception as e:
        logger.error(f"Ollama classification failed: {e}")
        return classify_fallback(message)

def classify_with_huggingface(message: str) -> Classification:
    """Use Hugging Face Inference API (free tier)"""
    if not HF_API_KEY:
        logger.warning("HF_API_KEY not set, using fallback")
        return classify_fallback(message)
    
    try:
        prompt = f"""<s>[INST] Classify this message's priority as urgent, high, normal, or low.
Also categorize it as work, personal, social, or marketing.

Message: {message}

Respond with JSON only:
{{"priority": "...", "category": "...", "reasoning": "..."}} [/INST]"""

        response = requests.post(
            f"{HF_API_URL}{HF_MODEL}",
            headers={"Authorization": f"Bearer {HF_API_KEY}"},
            json={"inputs": prompt, "parameters": {"max_new_tokens": 150}},
            timeout=10
        )
        
        if response.status_code != 200:
            raise Exception(f"HF API error: {response.text}")
        
        result_text = response.json()[0]['generated_text']
        
        # Extract JSON from response
        start_idx = result_text.find('{')
        end_idx = result_text.rfind('}') + 1
        if start_idx != -1 and end_idx > start_idx:
            json_str = result_text[start_idx:end_idx]
            result = json.loads(json_str)
            
            return Classification(
                priority=result.get('priority', 'normal'),
                category=result.get('category', 'personal'),
                requires_action=result.get('priority', 'normal') in ['urgent', 'high'],
                confidence=0.75,
                reasoning=result.get('reasoning', 'HuggingFace classification')
            )
        else:
            raise ValueError("No JSON found in response")
            
    except Exception as e:
        logger.error(f"HuggingFace classification failed: {e}")
        return classify_fallback(message)

def classify_fallback(message: str) -> Classification:
    """Rule-based fallback classification (always works)"""
    text = message.lower()
    
    # Keywords
    urgent_keywords = ['urgent', 'asap', 'emergency', 'critical', 'help', 'down', '!!!', 'immediately']
    high_keywords = ['important', 'deadline', 'meeting', 'client', 'soon', 'asap']
    work_keywords = ['meeting', 'project', 'deadline', 'client', 'work', 'report', 'presentation']
    
    urgent_count = sum(1 for kw in urgent_keywords if kw in text)
    high_count = sum(1 for kw in high_keywords if kw in text)
    
    # Determine priority
    if urgent_count >= 2 or '!!!' in message:
        priority = 'urgent'
        confidence = 0.85
        reasoning = f"Multiple urgent indicators: {urgent_count}"
    elif urgent_count >= 1:
        priority = 'urgent'
        confidence = 0.75
        reasoning = "Contains urgent keywords"
    elif high_count >= 1:
        priority = 'high'
        confidence = 0.70
        reasoning = "Contains high-priority keywords"
    elif '?' in text:
        priority = 'normal'
        confidence = 0.65
        reasoning = "Question detected"
    else:
        priority = 'low'
        confidence = 0.60
        reasoning = "No priority indicators"
    
    # Determine category
    category = 'work' if any(kw in text for kw in work_keywords) else 'personal'
    
    return Classification(
        priority=priority,
        category=category,
        requires_action=priority in ['urgent', 'high'],
        confidence=confidence,
        reasoning=f"Rule-based: {reasoning}"
    )

def classify_message_smart(message: str) -> Classification:
    """Smart classification: try Ollama, then HuggingFace, then fallback"""
    
    # Try Ollama first (fastest, local)
    if OLLAMA_AVAILABLE:
        try:
            return classify_with_ollama(message)
        except Exception as e:
            logger.warning(f"Ollama failed, trying fallback: {e}")
    
    # Try HuggingFace (free cloud API)
    if HF_API_KEY:
        try:
            return classify_with_huggingface(message)
        except Exception as e:
            logger.warning(f"HuggingFace failed, using fallback: {e}")
    
    # Fallback to rules (always works)
    return classify_fallback(message)

def decide_action(classification: Classification, user_status: str) -> str:
    """Decide what action to take based on classification and user status"""
    priority = classification.priority
    
    if user_status == 'dnd':
        if priority == 'urgent':
            return 'notify'  # Break through DND for urgent
        else:
            return 'auto_reply'  # Send auto-reply for others
    elif user_status == 'busy':
        if priority in ['urgent', 'high']:
            return 'remind'  # Remind later for important messages
        else:
            return 'none'  # Just store low-priority
    else:  # available
        return 'none'  # User will see normally

# ============================================
# API ENDPOINTS
# ============================================

@app.post("/api/messages/classify", response_model=ActionResponse)
async def classify_message_endpoint(message: IncomingMessage):
    """
    Main endpoint: Receive message, classify it, decide action
    """
    try:
        # 1. Classify the message
        classification = classify_message_smart(message.content)
        
        logger.info(
            f"📩 Message classified: {classification.priority} "
            f"(confidence: {classification.confidence:.2f}) "
            f"via {classification.reasoning}"
        )
        
        # 2. Get user status
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM user_status WHERE user_id = ?", ("default_user",))
        row = cursor.fetchone()
        user_status = row[0] if row else 'available'
        
        # 3. Decide action
        action_type = decide_action(classification, user_status)
        
        # 4. Store message
        cursor.execute("""
            INSERT OR REPLACE INTO messages 
            (id, platform, sender, content, timestamp, classification)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            message.id,
            message.platform,
            message.sender,
            message.content,
            message.timestamp,
            json.dumps(classification.dict())
        ))
        
        # 5. Store action
        cursor.execute("""
            INSERT INTO actions 
            (message_id, action_type, priority, action_data)
            VALUES (?, ?, ?, ?)
        """, (
            message.id,
            action_type,
            classification.priority,
            json.dumps({"classification": classification.dict()})
        ))
        
        conn.commit()
        conn.close()
        
        return ActionResponse(
            message_id=message.id,
            action_type=action_type,
            priority=classification.priority,
            classification=classification,
            status='pending'
        )
        
    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/user/status")
async def update_user_status(status: UserStatus):
    """Update user status (available/busy/dnd)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR REPLACE INTO user_status 
        (user_id, status, auto_reply_message, updated_at)
        VALUES (?, ?, ?, ?)
    """, (status.user_id, status.status, status.auto_reply_message, datetime.now()))
    
    conn.commit()
    conn.close()
    
    logger.info(f"✅ User status updated to: {status.status}")
    return {"success": True, "status": status.status}

@app.get("/api/user/status")
async def get_user_status(user_id: str = "default_user"):
    """Get current user status"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT status, auto_reply_message FROM user_status WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {"user_id": user_id, "status": row[0], "auto_reply_message": row[1]}
    else:
        return {"user_id": user_id, "status": "available", "auto_reply_message": None}

@app.get("/api/actions/pending")
async def get_pending_actions():
    """Get all pending actions"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT a.*, m.content, m.sender 
        FROM actions a
        JOIN messages m ON a.message_id = m.id
        WHERE a.status = 'pending'
        ORDER BY a.created_at DESC
        LIMIT 50
    """)
    
    actions = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return {"actions": actions, "count": len(actions)}

@app.get("/api/messages/recent")
async def get_recent_messages(limit: int = 20):
    """Get recent messages"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM messages 
        ORDER BY timestamp DESC 
        LIMIT ?
    """, (limit,))
    
    messages = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return {"messages": messages, "count": len(messages)}

@app.get("/api/stats")
async def get_stats():
    """Get system statistics"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM messages")
    total_messages = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM actions WHERE status = 'pending'")
    pending_actions = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT json_extract(classification, '$.priority') as priority, COUNT(*) as count
        FROM messages
        WHERE classification IS NOT NULL
        GROUP BY priority
    """)
    priority_counts = dict(cursor.fetchall())
    
    conn.close()
    
    return {
        "total_messages": total_messages,
        "pending_actions": pending_actions,
        "priority_breakdown": priority_counts,
        "ollama_enabled": OLLAMA_AVAILABLE,
        "ollama_model": OLLAMA_MODEL if OLLAMA_AVAILABLE else None,
        "classifier": "ollama" if OLLAMA_AVAILABLE else "huggingface" if HF_API_KEY else "rule-based"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "nexa-sidecar",
        "ollama_available": OLLAMA_AVAILABLE,
        "ollama_model": OLLAMA_MODEL if OLLAMA_AVAILABLE else None,
        "hf_available": HF_API_KEY is not None,
        "db_path": DB_PATH
    }

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚀 NEXA BEEPER SIDECAR STARTING")
    print("="*60)
    print(f"Ollama: {'✅ Available' if OLLAMA_AVAILABLE else '❌ Not available (using fallback)'}")
    print(f"Model: {OLLAMA_MODEL if OLLAMA_AVAILABLE else 'rule-based'}")
    print(f"Database: {DB_PATH}")
    print("="*60 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)