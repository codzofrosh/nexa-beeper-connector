# bridge/whatsapp/connector.py
"""
WhatsApp bridge connector that integrates with your existing bridge
"""
import asyncio
import aiohttp
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class WhatsAppConnector:
    """
    Connects mautrix-whatsapp to your existing sidecar
    """
    def __init__(self, sidecar_url: str = "http://localhost:8000"):
        self.sidecar_url = sidecar_url
        self.session = None
        
    async def initialize(self):
        """Setup HTTP session"""
        self.session = aiohttp.ClientSession()
        logger.info("WhatsApp connector initialized")
    
    async def handle_matrix_event(self, event: Dict[str, Any]):
        """
        Called when mautrix-whatsapp receives a WhatsApp message
        Send it to your existing sidecar API
        """
        try:
            # Transform Matrix event to your format
            message = self._transform_event(event)
            
            # Send to your existing app.py endpoint
            async with self.session.post(
                f"{self.sidecar_url}/api/messages/incoming",
                json=message
            ) as resp:
                if resp.status == 200:
                    action = await resp.json()
                    await self._execute_action(action, event)
                else:
                    logger.error(f"Sidecar returned {resp.status}")
                    
        except Exception as e:
            logger.error(f"Error handling WhatsApp message: {e}")
    
    def _transform_event(self, event: Dict) -> Dict:
        """
        Transform Matrix event to your message format
        Adapt this to match your existing message schema
        """
        return {
            'id': event.get('event_id'),
            'platform': 'whatsapp',
            'sender': event.get('sender'),
            'room_id': event.get('room_id'),
            'content': event.get('content', {}).get('body', ''),
            'timestamp': event.get('origin_server_ts', 0),
            'metadata': {}
        }
    
    async def _execute_action(self, action: Dict, original_event: Dict):
        """
        Execute the action returned by your sidecar
        This calls back to Matrix to send messages
        """
        action_type = action.get('action', {}).get('type')
        
        if action_type == 'auto_reply':
            await self._send_reply(
                original_event['room_id'],
                action['action']['message']
            )
        elif action_type == 'notify':
            # Trigger notification (use your existing notification system)
            pass
    
    async def _send_reply(self, room_id: str, message: str):
        """
        Send message back to WhatsApp via Matrix
        This would integrate with mautrix-whatsapp's send API
        """
        # TODO: Implement Matrix client send
        logger.info(f"Would send to {room_id}: {message}")
    
    async def cleanup(self):
        """Close session"""
        if self.session:
            await self.session.close()