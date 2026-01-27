# ai/hybrid_classifier.py - UPDATED with better error handling

"""
Hybrid classifier that combines multiple classification strategies.
Tries classifiers in order: local → cloud → rule-based
"""

from typing import Dict, Any, Optional
import logging
import asyncio

logger = logging.getLogger(__name__)

# Import rule-based (this should always work)
from ai.rule_based import RuleBasedClassifier

# Try to import optional classifiers
HAS_LOCAL = False
HAS_CLOUD = False
LocalClassifier = None
CloudClassifier = None

try:
    from ai.local_model import LocalClassifier
    HAS_LOCAL = True
    logger.info("✅ LocalClassifier imported")
except Exception as e:
    logger.warning(f"⚠️  LocalClassifier not available: {e}")
    HAS_LOCAL = False

try:
    from ai.cloud_classifier import CloudClassifier
    HAS_CLOUD = True
    logger.info("✅ CloudClassifier imported")
except Exception as e:
    logger.warning(f"⚠️  CloudClassifier not available: {e}")
    HAS_CLOUD = False


class HybridClassifier:
    """
    Intelligent classifier that tries multiple approaches.
    Falls back gracefully when classifiers fail.
    """
    
    def __init__(
        self,
        use_local: bool = True,
        use_cloud: bool = False,
        cloud_backend: str = "custom",
        cloud_api_key: Optional[str] = None,
        confidence_threshold: float = 0.7
    ):
        self.confidence_threshold = confidence_threshold
        self.classifiers = []
        
        # 1. Local model (fastest, works offline)
        if use_local and HAS_LOCAL and LocalClassifier is not None:
            try:
                local_classifier = LocalClassifier()
                self.classifiers.append(('local', local_classifier))
                logger.info("✅ Local classifier loaded")
            except Exception as e:
                logger.warning(f"⚠️  Failed to load local classifier: {e}")
        
        # 2. Cloud API (most accurate, requires internet)
        if use_cloud and HAS_CLOUD and CloudClassifier is not None:
            try:
                cloud_classifier = CloudClassifier(
                    backend=cloud_backend,
                    api_key=cloud_api_key
                )
                self.classifiers.append(('cloud', cloud_classifier))
                logger.info(f"✅ Cloud classifier loaded (backend: {cloud_backend})")
            except Exception as e:
                logger.warning(f"⚠️  Failed to load cloud classifier: {e}")
        
        # 3. Rule-based (always available, fallback)
        rule_classifier = RuleBasedClassifier()
        self.classifiers.append(('rule', rule_classifier))
        logger.info("✅ Rule-based classifier loaded")
        
        if not self.classifiers:
            raise RuntimeError("No classifiers available!")
        
        logger.info(f"Hybrid classifier initialized with {len(self.classifiers)} strategies")
    
    async def classify(
        self,
        message: str,
        force_cloud: bool = False,
        timeout: float = 5.0
    ) -> Dict[str, Any]:
        """
        Classify message using best available classifier.
        
        Args:
            message: Text to classify
            force_cloud: Skip local and use cloud only
            timeout: Max time per classifier
            
        Returns:
            Classification result with metadata
        """
        errors = []
        low_confidence_result = None
        
        for name, classifier in self.classifiers:
            # Skip non-cloud if forced
            if force_cloud and name != 'cloud':
                continue
            
            try:
                # Classify with timeout
                result = await asyncio.wait_for(
                    self._classify_with_classifier(classifier, message),
                    timeout=timeout
                )
                
                # Add metadata
                result['classifier_used'] = name
                result['timestamp'] = self._get_timestamp()
                
                # Check if result is confident enough
                confidence = result.get('confidence', 0.0)
                
                if confidence >= self.confidence_threshold:
                    logger.debug(
                        f"Classified with {name}: "
                        f"{result['priority']} (confidence: {confidence:.2f})"
                    )
                    return result
                else:
                    logger.debug(
                        f"{name} confidence too low ({confidence:.2f}), trying next..."
                    )
                    # Store this result in case all fail
                    low_confidence_result = result
                    
            except asyncio.TimeoutError:
                logger.warning(f"{name} classifier timed out after {timeout}s")
                errors.append((name, 'timeout'))
                
            except Exception as e:
                logger.warning(f"{name} classifier failed: {e}")
                errors.append((name, str(e)))
                continue
        
        # If we get here, either all failed or none met confidence threshold
        if low_confidence_result is not None:
            low_confidence_result['errors'] = errors
            low_confidence_result['fallback_reason'] = 'low_confidence'
            return low_confidence_result
        
        # Total failure - return safe defaults
        return {
            'priority': 'normal',
            'confidence': 0.3,
            'requires_action': False,
            'category': 'personal',
            'classifier_used': 'fallback',
            'errors': errors,
            'fallback_reason': 'all_failed',
            'timestamp': self._get_timestamp()
        }
    
    async def _classify_with_classifier(
        self,
        classifier,
        message: str
    ) -> Dict[str, Any]:
        """Helper to call classifier (async or sync)."""
        # Check if classifier has async method
        if hasattr(classifier, 'classify_async'):
            return await classifier.classify_async(message)
        elif asyncio.iscoroutinefunction(classifier.classify):
            return await classifier.classify(message)
        else:
            # Run sync method in executor to not block
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, classifier.classify, message)
    
    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()
    
    async def batch_classify(
        self,
        messages: list,
        max_concurrent: int = 5
    ) -> list:
        """
        Classify multiple messages concurrently.
        
        Args:
            messages: List of messages to classify
            max_concurrent: Max concurrent classifications
            
        Returns:
            List of classification results
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def classify_with_semaphore(msg):
            async with semaphore:
                return await self.classify(msg)
        
        tasks = [classify_with_semaphore(msg) for msg in messages]
        return await asyncio.gather(*tasks)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get classifier statistics."""
        return {
            'num_classifiers': len(self.classifiers),
            'available_classifiers': [name for name, _ in self.classifiers],
            'confidence_threshold': self.confidence_threshold
        }