# sidecar/message_service.py
"""
Unified message service combining classification and persistence.
Handles the complete flow: classify -> decide -> persist -> track.
"""

import logging
import json
import requests
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class MessageClassificationService:
    """Handles message classification with multiple backend strategies."""
    
    def __init__(self, ollama_url: str = "http://localhost:11435",
                 ollama_model: str = "llama3.2:1b",
                 use_ollama: bool = True,
                 hf_api_key: Optional[str] = None,
                 hf_model: str = "mistralai/Mistral-7B-Instruct-v0.2"):
        
        self.ollama_url = ollama_url
        self.ollama_model = ollama_model
        self.use_ollama = use_ollama
        self.hf_api_key = hf_api_key
        self.hf_model = hf_model
        self.ollama_available = False
        
        if self.use_ollama:
            self._test_ollama_connection()
    
    def _test_ollama_connection(self) -> bool:
        """Test if Ollama is available."""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=2)
            if response.status_code == 200:
                models = [model['name'] for model in response.json().get('models', [])]
                logger.info(f"Ollama connected. Available models: {models}")
                self.ollama_available = True
                return True
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
        
        self.ollama_available = False
        return False
    
    def classify(self, message: str) -> Dict[str, Any]:
        """
        Classify a message using the best available backend.
        Falls back through: Ollama -> HuggingFace -> Rule-based
        
        Returns:
            Classification dict with keys: priority, category, confidence, 
                                          reasoning, requires_action, classifier_used
        """
        # Try Ollama first
        if self.ollama_available:
            try:
                result = self._classify_with_ollama(message)
                result['classifier_used'] = 'ollama'
                return result
            except Exception as e:
                logger.warning(f"Ollama classification failed: {e}")
        
        # Try HuggingFace
        if self.hf_api_key:
            try:
                result = self._classify_with_huggingface(message)
                result['classifier_used'] = 'huggingface'
                return result
            except Exception as e:
                logger.warning(f"HuggingFace classification failed: {e}")
        
        # Fall back to rule-based
        result = self._classify_rule_based(message)
        result['classifier_used'] = 'rule-based'
        return result
    
    def _classify_with_ollama(self, message: str) -> Dict[str, Any]:
        """Classify using Ollama local LLM."""
        prompt = f"""Analyze this message and classify its priority.

Message: "{message}"

Respond with ONLY valid JSON in this exact format:
{{
    "priority": "urgent|high|normal|low",
    "category": "work|personal|social|marketing",
    "requires_action": true or false,
    "confidence": 0.0 to 1.0,
    "reasoning": "brief explanation"
}}"""
        
        response = requests.post(
            f"{self.ollama_url}/api/generate",
            json={
                "model": self.ollama_model,
                "prompt": prompt,
                "stream": False,
                "format": "json"
            },
            timeout=10
        )
        
        if response.status_code != 200:
            raise Exception(f"Ollama error: {response.text}")
        
        result_text = response.json()['response'].strip()
        
        # Extract JSON
        if "```json" in result_text:
            start = result_text.find("```json") + 7
            end = result_text.find("```", start)
            result_text = result_text[start:end].strip()
        elif "```" in result_text:
            start = result_text.find("```") + 3
            end = result_text.find("```", start)
            result_text = result_text[start:end].strip()
        
        result = json.loads(result_text)
        
        # Ensure required fields
        result.setdefault('priority', 'normal')
        result.setdefault('confidence', 0.7)
        result.setdefault('category', 'personal')
        result.setdefault('requires_action', result['priority'] in ['urgent', 'high'])
        
        return result
    
    def _classify_with_huggingface(self, message: str) -> Dict[str, Any]:
        """Classify using HuggingFace Inference API."""
        if not self.hf_api_key:
            raise ValueError("HF_API_KEY not set")
        
        prompt = f"""<s>[INST] Classify this message's priority as urgent, high, normal, or low.
Also categorize it as work, personal, social, or marketing.

Message: {message}

Respond with JSON only:
{{"priority": "...", "category": "...", "reasoning": "..."}} [/INST]"""
        
        response = requests.post(
            f"https://api-inference.huggingface.co/models/{self.hf_model}",
            headers={"Authorization": f"Bearer {self.hf_api_key}"},
            json={"inputs": prompt, "parameters": {"max_new_tokens": 150}},
            timeout=10
        )
        
        if response.status_code != 200:
            raise Exception(f"HF API error: {response.text}")
        
        result_text = response.json()[0]['generated_text']
        
        # Extract JSON
        start_idx = result_text.find('{')
        end_idx = result_text.rfind('}') + 1
        if start_idx != -1 and end_idx > start_idx:
            json_str = result_text[start_idx:end_idx]
            result = json.loads(json_str)
            
            result.setdefault('priority', 'normal')
            result.setdefault('category', 'personal')
            result.setdefault('confidence', 0.75)
            result.setdefault('requires_action', result['priority'] in ['urgent', 'high'])
            
            return result
        else:
            raise ValueError("No JSON found in response")
    
    def _classify_rule_based(self, message: str) -> Dict[str, Any]:
        """Rule-based fallback classification."""
        text = message.lower()
        
        urgent_keywords = ['urgent', 'asap', 'emergency', 'critical', 'help', 'down', '!!!']
        high_keywords = ['important', 'deadline', 'meeting', 'client', 'soon']
        work_keywords = ['meeting', 'project', 'deadline', 'client', 'work', 'report']
        
        urgent_count = sum(1 for kw in urgent_keywords if kw in text)
        high_count = sum(1 for kw in high_keywords if kw in text)
        
        # Determine priority
        if urgent_count >= 2 or '!!!' in message:
            priority = 'urgent'
            confidence = 0.85
            reasoning = f"Multiple urgent indicators ({urgent_count})"
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
        
        return {
            "priority": priority,
            "category": category,
            "confidence": confidence,
            "reasoning": f"Rule-based: {reasoning}",
            "requires_action": priority in ['urgent', 'high']
        }


class ActionDecisionService:
    """Decides what action to take based on classification and user status."""
    
    @staticmethod
    def decide_action(priority: str, user_status: str) -> str:
        """
        Decide action based on message priority and user status.
        
        Args:
            priority: Classification priority (urgent, high, normal, low)
            user_status: User status (available, busy, dnd)
        
        Returns:
            Action type: notify, remind, auto_reply, none
        """
        if user_status == 'dnd':
            if priority == 'urgent':
                return 'notify'  # Break through DND for urgent
            else:
                return 'auto_reply'  # Send auto-reply for others
        
        elif user_status == 'busy':
            if priority in ['urgent', 'high']:
                return 'remind'  # Remind later for important
            else:
                return 'none'  # Just store low-priority
        
        else:  # available
            return 'none'  # User will see normally


class UnifiedMessageService:
    """
    Main service combining classification, decision-making, and persistence.
    Provides a single unified interface for the complete message flow.
    """
    
    def __init__(self, database_service, classification_service, action_decision_service=None):
        self.db = database_service
        self.classifier = classification_service
        self.decision_maker = action_decision_service or ActionDecisionService()
    
    def process_message(self, message_id: str, platform: str, sender: str,
                       content: str, timestamp: int, user_id: str = "default_user",
                       room_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Complete message processing pipeline - IDEMPOTENT:
        1. Check if message_id exists (DUPLICATE check FIRST)
        2. If NEW: Classify -> Decide -> Persist
        3. If DUPLICATE: Return metadata only (NO classification, NO LLM)
        
        Idempotency is binary: NEW or DUPLICATE. Never both.
        
        Args:
            message_id: Unique message ID
            platform: Platform source
            sender: Sender identifier
            content: Message content
            timestamp: Unix timestamp
            user_id: User being messaged
            room_id: Optional room/channel ID
        
        Returns:
            NEW: {status: "success", message_id, classification, action_id, action_type, priority}
            DUPLICATE: {status: "duplicate", message_id, reason: "message_id already exists"}
        """
        try:
            # CRITICAL: Check for duplicate FIRST, before any classification
            existing = self.db.message_exists(message_id)
            
            if existing:
                logger.warning(f"Duplicate message: {message_id}")
                return {
                    "status": "duplicate",
                    "message_id": message_id,
                    "reason": "message_id already exists"
                }
            
            # NEW message - now classify
            logger.info(f"Processing NEW message: {message_id}")
            classification = self.classifier.classify(content)
            
            # Decide action
            user_status_data = self.db.get_user_status(user_id)
            user_status = user_status_data.get('status', 'available')
            action_type = self.decision_maker.decide_action(classification['priority'], user_status)
            
            logger.info(f"Decision: {action_type} for {classification['priority']} message")
            
            # Store message with classification
            message_stored = self.db.store_message(
                message_id=message_id,
                platform=platform,
                sender=sender,
                content=content,
                timestamp=timestamp,
                room_id=room_id,
                classification=classification
            )
            
            if not message_stored:
                # Should not happen after our check, but handle it
                logger.error(f"Failed to store message {message_id}")
                return {
                    "status": "error",
                    "message_id": message_id,
                    "reason": "failed to store"
                }
            
            # Store action
            action_id = self.db.store_action(
                message_id=message_id,
                action_type=action_type,
                priority=classification['priority'],
                action_data={"user_status": user_status},
                classification_data=classification
            )
            
            logger.info(f"Message processed: {message_id} -> Action {action_id}")
            
            return {
                "status": "success",
                "message_id": message_id,
                "action_id": action_id,
                "action_type": action_type,
                "priority": classification['priority'],
                "classification": classification,
                "user_status": user_status
            }
        
        except Exception as e:
            logger.error(f"Message processing failed: {e}", exc_info=True)
            return {
                "status": "error",
                "message_id": message_id,
                "error": str(e)
            }
