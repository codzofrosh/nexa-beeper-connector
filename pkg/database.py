# pkg/database.py or create a new file

"""
Database operations for storing messages and actions.
Uses SQLite for simplicity (can switch to PostgreSQL later).
"""

import sqlite3
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger(__name__)

DB_PATH = "data/nexa.db"


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_database():
    """Initialize database schema."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                sender TEXT NOT NULL,
                sender_name TEXT,
                room_id TEXT NOT NULL,
                room_name TEXT,
                content TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                is_reply BOOLEAN DEFAULT 0,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Actions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                remind_at TIMESTAMP,
                executed_at TIMESTAMP,
                classification TEXT,
                action_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (message_id) REFERENCES messages(id)
            )
        """)
        
        # User preferences table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id TEXT PRIMARY KEY,
                status TEXT DEFAULT 'available',
                auto_reply_template TEXT,
                preferences TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_actions_status ON actions(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_actions_remind_at ON actions(remind_at)")
        
        conn.commit()
        logger.info("✅ Database initialized")


async def store_message(message_data: Dict[str, Any]) -> bool:
    """Store incoming message."""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO messages 
                (id, platform, sender, sender_name, room_id, room_name, 
                 content, timestamp, is_reply, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                message_data['id'],
                message_data['platform'],
                message_data['sender'],
                message_data.get('sender_name'),
                message_data['room_id'],
                message_data.get('room_name'),
                message_data['content'],
                message_data['timestamp'],
                message_data.get('is_reply', False),
                json.dumps(message_data.get('metadata', {}))
            ))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Failed to store message: {e}")
        return False


async def store_action(
    message_id: str,
    action: Dict[str, Any],
    classification: Dict[str, Any]
) -> Optional[int]:
    """Store action to be executed."""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO actions 
                (message_id, action_type, remind_at, classification, action_data)
                VALUES (?, ?, ?, ?, ?)
            """, (
                message_id,
                action['type'],
                action.get('remind_at'),
                json.dumps(classification),
                json.dumps(action)
            ))
            conn.commit()
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"Failed to store action: {e}")
        return None


async def get_user_preferences(user_id: str) -> Dict[str, Any]:
    """Get user preferences or return defaults."""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM user_preferences WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            
            if row:
                return {
                    'status': row['status'],
                    'auto_reply_template': row['auto_reply_template'],
                    'preferences': json.loads(row['preferences'] or '{}')
                }
    except Exception as e:
        logger.error(f"Failed to get user preferences: {e}")
    
    # Return defaults
    return {
        'status': 'available',
        'auto_reply_template': "I'm currently unavailable. I'll get back to you soon!",
        'preferences': {}
    }

init_database()
