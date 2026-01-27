# ingestion.py - ENHANCED VERSION

"""
Message ingestion pipeline.
Receives Matrix events, classifies them using AI, and decides actions.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from nio import AsyncClient, MatrixRoom, RoomMessageText

# Import your AI classifier
from ai.hybrid_classifier import HybridClassifier
from ai.rule_based import RuleBasedClassifier

# Database imports (add to your existing imports)
from pkg.database import (
    store_message,
    store_action,
    get_user_preferences,
)

logger = logging.getLogger(__name__)

# Initialize AI classifier globally (loaded once at startup)
try:
    classifier = HybridClassifier(use_local=True, use_cloud=False)
    logger.info("✅ AI Classifier initialized")
except Exception as e:
    logger.warning(f"⚠️  Using rule-based classifier fallback: {e}")
    classifier = RuleBasedClassifier()


async def handle_message(client: AsyncClient, room: MatrixRoom, event: RoomMessageText):
    """
    Called by app.py when a message arrives.
    
    Original flow:
    1. Extract message
    2. [Your existing logic here]
    
    NEW Enhanced flow:
    1. Extract message
    2. Classify with AI ← NEW
    3. Decide action based on classification ← NEW
    4. Execute or schedule action ← NEW
    5. [Your existing logic continues]
    """
    
    # Skip messages from the bot itself
    if event.sender == client.user_id:
        return
    
    try:
        # 1. Extract message data (your existing logic)
        message_data = extract_message_data(room, event)
        
        # 2. Store raw message (optional but recommended)
        await store_message(message_data)
        
        # 3. NEW: Classify the message using AI
        classification = await classify_message(message_data['content'])
        
        # 4. NEW: Get user preferences (status, auto-reply settings, etc.)
        user_prefs = await get_user_preferences(client.user_id)
        
        # 5. NEW: Decide what action to take
        action = decide_action(classification, user_prefs, message_data)
        
        # 6. NEW: Store the action for execution
        if action['type'] != 'none':
            await store_action(message_data['id'], action, classification)
        
        # 7. NEW: Execute immediate actions (auto-reply, notify)
        if action.get('execute_immediately'):
            await execute_action(client, room, action, message_data)
        
        # 8. Your existing logic continues here...
        # (Keep any other processing you were doing)
        
        logger.info(
            f"📩 Message from {event.sender} in {room.display_name} "
            f"[Priority: {classification['priority']}] "
            f"[Action: {action['type']}]"
        )
        
    except Exception as e:
        logger.error(f"❌ Error handling message: {e}", exc_info=True)


def extract_message_data(room: MatrixRoom, event: RoomMessageText) -> Dict[str, Any]:
    """
    Extract structured data from Matrix event.
    Adapt this based on what data you need.
    """
    # Detect platform from room ID or display name
    platform = detect_platform(room)
    
    return {
        'id': event.event_id,
        'platform': platform,
        'sender': event.sender,
        'sender_name': room.user_name(event.sender) or event.sender,
        'room_id': room.room_id,
        'room_name': room.display_name or room.room_id,
        'content': event.body,
        'timestamp': event.server_timestamp,
        'is_reply': hasattr(event, 'relates_to') and event.relates_to is not None,
        'metadata': {
            'formatted_body': getattr(event, 'formatted_body', None),
            'source': event.source,
        }
    }


def detect_platform(room: MatrixRoom) -> str:
    """
    Detect which messaging platform this message came from.
    Based on room ID patterns used by mautrix bridges.
    """
    room_id = room.room_id.lower()
    display_name = (room.display_name or '').lower()
    
    # mautrix-whatsapp rooms typically contain 'whatsapp'
    if 'whatsapp' in room_id or 'whatsapp' in display_name:
        return 'whatsapp'
    
    # mautrix-telegram rooms
    if 'telegram' in room_id or 'telegram' in display_name:
        return 'telegram'
    
    # mautrix-signal rooms
    if 'signal' in room_id or 'signal' in display_name:
        return 'signal'
    
    # Default to matrix for native Matrix messages
    return 'matrix'


async def classify_message(content: str) -> Dict[str, Any]:
    """
    Classify message using AI or rule-based system.
    """
    try:
        classification = await classifier.classify(content)
        return classification
    except Exception as e:
        logger.error(f"Classification failed: {e}")
        # Fallback to safe defaults
        return {
            'priority': 'normal',
            'confidence': 0.3,
            'requires_action': False,
            'classifier_used': 'fallback',
            'error': str(e)
        }


def decide_action(
    classification: Dict[str, Any],
    user_prefs: Dict[str, Any],
    message_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Business logic: decide what action to take based on:
    - Message classification (priority, sentiment, etc.)
    - User preferences (status, auto-reply settings)
    - Message context (sender, platform, time)
    """
    
    user_status = user_prefs.get('status', 'available')
    priority = classification['priority']
    platform = message_data['platform']
    
    # Rule 1: User is in DND mode
    if user_status == 'dnd':
        if priority == 'urgent':
            # Urgent messages break through DND but send notification
            return {
                'type': 'notify',
                'execute_immediately': True,
                'notification': {
                    'title': f"Urgent message from {message_data['sender_name']}",
                    'body': message_data['content'][:100],
                    'priority': 'high'
                },
                'reason': 'urgent_during_dnd'
            }
        else:
            # Non-urgent: auto-reply and remind later
            return {
                'type': 'auto_reply',
                'execute_immediately': True,
                'message': user_prefs.get(
                    'auto_reply_template',
                    "I'm currently unavailable. I'll get back to you soon!"
                ),
                'remind_at': get_reminder_time(user_prefs),
                'reason': 'dnd_auto_reply'
            }
    
    # Rule 2: User is busy
    elif user_status == 'busy':
        if priority in ['urgent', 'high']:
            # Important messages: remind soon
            return {
                'type': 'remind',
                'execute_immediately': False,
                'remind_at': get_reminder_time(user_prefs, offset_minutes=15),
                'reason': 'busy_important_message'
            }
        else:
            # Normal messages: silent
            return {
                'type': 'none',
                'reason': 'busy_normal_message'
            }
    
    # Rule 3: User is available
    else:
        # Just notify normally (your existing behavior)
        return {
            'type': 'none',
            'reason': 'user_available'
        }


async def execute_action(
    client: AsyncClient,
    room: MatrixRoom,
    action: Dict[str, Any],
    message_data: Dict[str, Any]
):
    """
    Execute immediate actions like auto-reply or notifications.
    """
    action_type = action['type']
    
    if action_type == 'auto_reply':
        await send_auto_reply(client, room, action['message'], message_data)
    
    elif action_type == 'notify':
        await send_notification(action['notification'], message_data)
    
    # Other action types are handled by the executor service


async def send_auto_reply(
    client: AsyncClient,
    room: MatrixRoom,
    reply_text: str,
    original_message: Dict[str, Any]
):
    """
    Send auto-reply back to the room.
    """
    try:
        # Send as a reply to the original message
        content = {
            "msgtype": "m.text",
            "body": reply_text,
            "m.relates_to": {
                "m.in_reply_to": {
                    "event_id": original_message['id']
                }
            }
        }
        
        response = await client.room_send(
            room_id=room.room_id,
            message_type="m.room.message",
            content=content
        )
        
        logger.info(f"🤖 Sent auto-reply to {room.display_name}")
        return response
        
    except Exception as e:
        logger.error(f"Failed to send auto-reply: {e}")


async def send_notification(notification: Dict[str, Any], message_data: Dict[str, Any]):
    """
    Send push notification to user's device.
    This would integrate with FCM/APNS for mobile.
    """
    # TODO: Implement push notification
    # For now, just log it
    logger.info(f"🔔 Notification: {notification['title']}")
    pass


def get_reminder_time(user_prefs: Dict[str, Any], offset_minutes: int = 60) -> str:
    """
    Calculate when to remind the user based on their preferences.
    """
    from datetime import datetime, timedelta
    
    # Default: remind in 1 hour
    remind_time = datetime.now() + timedelta(minutes=offset_minutes)
    
    # TODO: Consider user's active hours, calendar, etc.
    
    return remind_time.isoformat()