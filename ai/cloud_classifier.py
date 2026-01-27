# ai/cloud_classifier.py

"""
Cloud-based AI classifier.
Supports multiple backends: OpenAI, Anthropic Claude, Hugging Face, or custom API.
"""

import logging
import aiohttp
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CloudClassifier:
    """
    Cloud-based message classifier with multiple backend options.
    """
    
    def __init__(
        self,
        backend: str = "custom",  # "openai", "anthropic", "huggingface", "custom"
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.backend = backend
        self.api_key = api_key
        self.api_url = api_url
        self.model = model
        
        # Rate limiting
        self.last_request_time = None
        self.min_request_interval = 0.1  # seconds between requests
        
        # Configure based on backend
        self._configure_backend()
    
    def _configure_backend(self):
        """Configure settings based on backend type."""
        if self.backend == "openai":
            self.api_url = self.api_url or "https://api.openai.com/v1/chat/completions"
            self.model = self.model or "gpt-3.5-turbo"
            
        elif self.backend == "anthropic":
            self.api_url = self.api_url or "https://api.anthropic.com/v1/messages"
            self.model = self.model or "claude-3-haiku-20240307"
            
        elif self.backend == "huggingface":
            # Hugging Face Inference API
            self.api_url = self.api_url or "https://api-inference.huggingface.co/models/distilbert-base-uncased"
            
        elif self.backend == "custom":
            # Your own FastAPI backend
            self.api_url = self.api_url or "http://localhost:8001/classify"
        
        else:
            raise ValueError(f"Unknown backend: {self.backend}")
    
    async def classify(self, message: str) -> Dict[str, Any]:
        """
        Classify message using cloud API.
        
        Args:
            message: Text message to classify
            
        Returns:
            Classification result
        """
        # Rate limiting
        await self._rate_limit()
        
        try:
            if self.backend == "openai":
                return await self._classify_openai(message)
            elif self.backend == "anthropic":
                return await self._classify_anthropic(message)
            elif self.backend == "huggingface":
                return await self._classify_huggingface(message)
            elif self.backend == "custom":
                return await self._classify_custom(message)
                
        except Exception as e:
            logger.error(f"Cloud classification failed: {e}")
            raise
    
    async def classify_async(self, message: str) -> Dict[str, Any]:
        """Async wrapper (already async)."""
        return await self.classify(message)
    
    async def _rate_limit(self):
        """Simple rate limiting."""
        import asyncio
        
        if self.last_request_time:
            elapsed = (datetime.now() - self.last_request_time).total_seconds()
            if elapsed < self.min_request_interval:
                await asyncio.sleep(self.min_request_interval - elapsed)
        
        self.last_request_time = datetime.now()
    
    async def _classify_openai(self, message: str) -> Dict[str, Any]:
        """Classify using OpenAI API."""
        prompt = self._build_classification_prompt(message)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a message priority classifier. Classify messages as: urgent, high, normal, or low priority. Respond ONLY with valid JSON."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.3,
            "max_tokens": 150
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"OpenAI API error: {error_text}")
                
                data = await response.json()
                result_text = data['choices'][0]['message']['content']
                
                # Parse JSON response
                return self._parse_classification_response(result_text)
    
    async def _classify_anthropic(self, message: str) -> Dict[str, Any]:
        """Classify using Anthropic Claude API."""
        prompt = self._build_classification_prompt(message)
        
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "max_tokens": 150,
            "messages": [
                {
                    "role": "user",
                    "content": f"Classify this message priority. Respond ONLY with JSON.\n\n{prompt}"
                }
            ]
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Anthropic API error: {error_text}")
                
                data = await response.json()
                result_text = data['content'][0]['text']
                
                return self._parse_classification_response(result_text)
    
    async def _classify_huggingface(self, message: str) -> Dict[str, Any]:
        """Classify using Hugging Face Inference API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        
        payload = {
            "inputs": message
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"HuggingFace API error: {error_text}")
                
                data = await response.json()
                
                # Hugging Face returns different formats depending on model
                # This is a generic parser - adapt to your specific model
                return self._parse_huggingface_response(data, message)
    
    async def _classify_custom(self, message: str) -> Dict[str, Any]:
        """Classify using your custom API endpoint."""
        payload = {
            "message": message,
            "return_probabilities": True
        }
        
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Custom API error: {error_text}")
                
                return await response.json()
    
    def _build_classification_prompt(self, message: str) -> str:
        """Build classification prompt for LLMs."""
        return f"""
Classify the following message's priority and category.

Message: "{message}"

Respond with JSON in this exact format:
{{
    "priority": "urgent|high|normal|low",
    "category": "work|personal|marketing|social",
    "requires_action": true|false,
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
}}
""".strip()
    
    def _parse_classification_response(self, response_text: str) -> Dict[str, Any]:
        """Parse JSON response from LLM."""
        try:
            # Try to extract JSON from response
            # Some models wrap JSON in markdown code blocks
            response_text = response_text.strip()
            
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                response_text = response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                response_text = response_text[start:end].strip()
            
            result = json.loads(response_text)
            
            # Add metadata
            result['classifier_used'] = f'cloud-{self.backend}'
            
            # Ensure required fields
            if 'priority' not in result:
                result['priority'] = 'normal'
            if 'confidence' not in result:
                result['confidence'] = 0.7
            if 'requires_action' not in result:
                result['requires_action'] = result['priority'] in ['urgent', 'high']
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {response_text}")
            # Return fallback
            return {
                'priority': 'normal',
                'confidence': 0.5,
                'requires_action': False,
                'classifier_used': f'cloud-{self.backend}-fallback',
                'error': str(e)
            }
    
    def _parse_huggingface_response(self, data: Any, message: str) -> Dict[str, Any]:
        """Parse Hugging Face response (varies by model)."""
        # This is model-dependent - adapt to your specific model
        # Example for sentiment analysis models
        try:
            if isinstance(data, list) and len(data) > 0:
                top_result = data[0][0] if isinstance(data[0], list) else data[0]
                
                label = top_result.get('label', 'NEUTRAL')
                score = top_result.get('score', 0.5)
                
                # Map sentiment to priority (example mapping)
                priority_map = {
                    'NEGATIVE': 'high',
                    'NEUTRAL': 'normal',
                    'POSITIVE': 'low'
                }
                
                return {
                    'priority': priority_map.get(label, 'normal'),
                    'confidence': score,
                    'category': 'personal',
                    'requires_action': label == 'NEGATIVE',
                    'classifier_used': 'cloud-huggingface'
                }
        except Exception as e:
            logger.error(f"HuggingFace parse error: {e}")
        
        # Fallback
        return {
            'priority': 'normal',
            'confidence': 0.5,
            'requires_action': False,
            'classifier_used': 'cloud-huggingface-fallback'
        }


if __name__ == "__main__":
    # Test the classifier
    import asyncio
    
    async def test():
        print("Testing CloudClassifier...")
        print("Note: This will fail without a running backend or API key\n")
        
        # Test with custom backend (no API key needed if you have local server)
        classifier = CloudClassifier(
            backend="custom",
            api_url="http://localhost:8001/classify"
        )
        
        test_messages = [
            "URGENT: Production server is down!",
            "Can we meet tomorrow?",
            "Thanks for the update",
        ]
        
        for msg in test_messages:
            try:
                result = await classifier.classify(msg)
                print(f"Message: {msg}")
                print(f"Priority: {result['priority']}")
                print(f"Confidence: {result['confidence']:.2f}\n")
            except Exception as e:
                print(f"Error (expected if no backend): {e}\n")
    
    # Uncomment to test
    # asyncio.run(test())
    print("CloudClassifier module loaded successfully")
    print("To test, set up a backend and uncomment asyncio.run(test())")