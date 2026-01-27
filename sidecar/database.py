# sidecar/database.py
"""
Unified database service for message classification and action persistence.
Consolidates schema management, idempotency, and state tracking.
"""

import sqlite3
import threading
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class DatabaseService:
    """Manages all database operations with thread-safe access."""
    
    def __init__(self, db_path: str = "data/nexa.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_schema()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a new database connection."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_schema(self):
        """Initialize database schema with all required tables."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            try:
                # Messages table - stores incoming messages with classification
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS messages (
                        id TEXT PRIMARY KEY,
                        platform TEXT NOT NULL,
                        sender TEXT NOT NULL,
                        room_id TEXT,
                        content TEXT NOT NULL,
                        timestamp INTEGER NOT NULL,
                        classification TEXT,
                        classifier_used TEXT,
                        confidence REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Actions table - stores decisions and execution state
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS actions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        message_id TEXT NOT NULL UNIQUE,
                        action_type TEXT NOT NULL,
                        priority TEXT NOT NULL,
                        status TEXT DEFAULT 'PENDING',
                        action_data TEXT,
                        classification_data TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        executed_at TIMESTAMP,
                        retry_count INTEGER DEFAULT 0,
                        last_error TEXT,
                        FOREIGN KEY (message_id) REFERENCES messages(id)
                    )
                """)
                
                # User status table - tracks user availability
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_status (
                        user_id TEXT PRIMARY KEY,
                        status TEXT DEFAULT 'available',
                        auto_reply_message TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Deduplication cache - for idempotency tracking
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS message_cache (
                        message_id TEXT PRIMARY KEY,
                        platform TEXT NOT NULL,
                        sender TEXT NOT NULL,
                        timestamp INTEGER NOT NULL,
                        cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                conn.commit()
                logger.info("Database schema initialized successfully")
                
            except Exception as e:
                logger.error(f"Schema initialization failed: {e}")
                conn.rollback()
                raise
            finally:
                conn.close()
    
    def message_exists(self, message_id: str) -> bool:
        """
        Check if a message already exists (duplicate check).
        
        Args:
            message_id: Message ID to check
            
        Returns:
            True if message exists, False otherwise
        """
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT 1 FROM messages WHERE id = ? LIMIT 1", (message_id,))
                exists = cursor.fetchone() is not None
                conn.close()
                return exists
            except Exception as e:
                logger.error(f"Failed to check message existence: {e}")
                conn.close()
                return False
    
    def store_message(self, message_id: str, platform: str, sender: str, 
                     content: str, timestamp: int, room_id: Optional[str] = None,
                     classification: Optional[Dict] = None) -> bool:
        """
        Store an incoming message.
        
        Args:
            message_id: Unique message identifier
            platform: Platform source (e.g., 'matrix', 'whatsapp')
            sender: Sender identifier
            content: Message content
            timestamp: Unix timestamp
            room_id: Optional room/channel ID
            classification: Optional classification data
        
        Returns:
            True if stored successfully, False if duplicate
        """
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            try:
                classification_json = json.dumps(classification) if classification else None
                classifier_used = classification.get('classifier_used') if classification else None
                confidence = classification.get('confidence') if classification else None
                
                cursor.execute("""
                    INSERT OR IGNORE INTO messages 
                    (id, platform, sender, room_id, content, timestamp, 
                     classification, classifier_used, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (message_id, platform, sender, room_id, content, timestamp,
                      classification_json, classifier_used, confidence))
                
                conn.commit()
                rows_inserted = cursor.rowcount
                
                if rows_inserted > 0:
                    logger.info(f"Message stored: {message_id}")
                    return True
                else:
                    logger.info(f"Duplicate message ignored: {message_id}")
                    return False
                    
            except Exception as e:
                logger.error(f"Failed to store message {message_id}: {e}")
                conn.rollback()
                return False
            finally:
                conn.close()
    
    def store_action(self, message_id: str, action_type: str, priority: str,
                    action_data: Optional[Dict] = None,
                    classification_data: Optional[Dict] = None) -> Optional[int]:
        """
        Store an action decision for a message (with deduplication).
        
        Args:
            message_id: ID of the message this action is for
            action_type: Type of action (notify, escalate, suppress, etc.)
            priority: Priority level
            action_data: Additional action metadata
            classification_data: Classification details
        
        Returns:
            Action ID if successful, None if duplicate
        """
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            try:
                action_json = json.dumps(action_data) if action_data else None
                classification_json = json.dumps(classification_data) if classification_data else None
                
                cursor.execute("""
                    INSERT INTO actions 
                    (message_id, action_type, priority, action_data, classification_data, status)
                    VALUES (?, ?, ?, ?, ?, 'PENDING')
                """, (message_id, action_type, priority, action_json, classification_json))
                
                conn.commit()
                action_id = cursor.lastrowid
                logger.info(f"Action stored: {action_id} for message {message_id}")
                return action_id
                
            except sqlite3.IntegrityError:
                logger.info(f"Duplicate action ignored for message: {message_id}")
                return None
            except Exception as e:
                logger.error(f"Failed to store action for {message_id}: {e}")
                conn.rollback()
                return None
            finally:
                conn.close()
    
    def get_message(self, message_id: str) -> Optional[Dict]:
        """Retrieve a message by ID."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            try:
                cursor.execute("SELECT * FROM messages WHERE id = ?", (message_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
            finally:
                conn.close()
    
    def get_action(self, message_id: str) -> Optional[Dict]:
        """Retrieve an action by message ID."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            try:
                cursor.execute("SELECT * FROM actions WHERE message_id = ?", (message_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
            finally:
                conn.close()
    
    def get_pending_actions(self, limit: int = 50) -> List[Dict]:
        """Get all pending actions."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            try:
                cursor.execute("""
                    SELECT a.*, m.content, m.sender, m.platform
                    FROM actions a
                    JOIN messages m ON a.message_id = m.id
                    WHERE a.status = 'PENDING'
                    ORDER BY a.created_at ASC
                    LIMIT ?
                """, (limit,))
                return [dict(row) for row in cursor.fetchall()]
            finally:
                conn.close()
    
    def get_recent_messages(self, limit: int = 20) -> List[Dict]:
        """Get recent messages with their classifications."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            try:
                cursor.execute("""
                    SELECT * FROM messages
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,))
                return [dict(row) for row in cursor.fetchall()]
            finally:
                conn.close()
    
    def update_action_status(self, action_id: int, status: str, 
                            executed_at: Optional[int] = None,
                            error: Optional[str] = None) -> bool:
        """Update action status after execution."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            try:
                if executed_at is None and status == 'COMPLETED':
                    executed_at = int(datetime.now().timestamp())
                
                cursor.execute("""
                    UPDATE actions
                    SET status = ?, executed_at = ?, last_error = ?
                    WHERE id = ?
                """, (status, executed_at, error, action_id))
                
                conn.commit()
                return cursor.rowcount > 0
            except Exception as e:
                logger.error(f"Failed to update action {action_id}: {e}")
                conn.rollback()
                return False
            finally:
                conn.close()
    
    def update_user_status(self, user_id: str, status: str, 
                          auto_reply: Optional[str] = None) -> bool:
        """Update user availability status."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO user_status 
                    (user_id, status, auto_reply_message, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """, (user_id, status, auto_reply))
                
                conn.commit()
                return True
            except Exception as e:
                logger.error(f"Failed to update user status: {e}")
                conn.rollback()
                return False
            finally:
                conn.close()
    
    def get_user_status(self, user_id: str) -> Dict:
        """Get current user status."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            try:
                cursor.execute(
                    "SELECT status, auto_reply_message FROM user_status WHERE user_id = ?",
                    (user_id,)
                )
                row = cursor.fetchone()
                if row:
                    return {"status": row[0], "auto_reply": row[1]}
                return {"status": "available", "auto_reply": None}
            finally:
                conn.close()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get system statistics."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            try:
                # Total messages
                cursor.execute("SELECT COUNT(*) FROM messages")
                total_messages = cursor.fetchone()[0]
                
                # Pending actions
                cursor.execute("SELECT COUNT(*) FROM actions WHERE status = 'PENDING'")
                pending_actions = cursor.fetchone()[0]
                
                # Priority breakdown
                cursor.execute("""
                    SELECT priority, COUNT(*) as count
                    FROM actions
                    GROUP BY priority
                """)
                priority_breakdown = dict(cursor.fetchall())
                
                # Classifier breakdown
                cursor.execute("""
                    SELECT classifier_used, COUNT(*) as count
                    FROM messages
                    WHERE classifier_used IS NOT NULL
                    GROUP BY classifier_used
                """)
                classifier_breakdown = dict(cursor.fetchall())
                
                return {
                    "total_messages": total_messages,
                    "pending_actions": pending_actions,
                    "priority_breakdown": priority_breakdown,
                    "classifier_breakdown": classifier_breakdown
                }
            finally:
                conn.close()
    
    def cleanup_old_cache(self, ttl_seconds: int = 300):
        """Clean up old deduplication cache entries."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            try:
                cursor.execute("""
                    DELETE FROM message_cache
                    WHERE datetime(cached_at) < datetime('now', '-' || ? || ' seconds')
                """, (ttl_seconds,))
                
                conn.commit()
                if cursor.rowcount > 0:
                    logger.debug(f"Cleaned {cursor.rowcount} cache entries")
            except Exception as e:
                logger.error(f"Cache cleanup failed: {e}")
                conn.rollback()
            finally:
                conn.close()
