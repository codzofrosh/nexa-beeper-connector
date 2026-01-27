# ai/rule_based.py

"""
Rule-based message classifier.
No ML required - uses keywords and patterns.
"""

import re
from typing import Dict, Any


class RuleBasedClassifier:
    """
    Simple rule-based classifier that works offline and requires no training.
    """
    
    def __init__(self):
        self.urgent_patterns = [
            r'\burgent\b',
            r'\basap\b',
            r'\bemergency\b',
            r'\bcritical\b',
            r'\bhelp\b',
            r'\bdown\b',
            r'\berror\b',
            r'\bfailed\b',
            r'!!!+',
            r'\bimmediately\b',
        ]
        
        self.work_patterns = [
            r'\bmeeting\b',
            r'\bdeadline\b',
            r'\bproject\b',
            r'\bclient\b',
            r'\bpresentation\b',
            r'\breview\b',
            r'\btask\b',
        ]
    
    def classify(self, message: str) -> Dict[str, Any]:
        """
        Classify message based on keyword patterns.
        """
        text = message.lower()
        
        # Calculate urgency score
        urgency_score = sum(
            1 for pattern in self.urgent_patterns
            if re.search(pattern, text, re.IGNORECASE)
        )
        
        # Calculate work-related score
        work_score = sum(
            1 for pattern in self.work_patterns
            if re.search(pattern, text, re.IGNORECASE)
        )
        
        # Determine priority
        if urgency_score >= 2:
            priority = 'urgent'
        elif urgency_score >= 1 or work_score >= 2:
            priority = 'high'
        elif work_score >= 1:
            priority = 'normal'
        else:
            priority = 'low'
        
        # Check if requires immediate action
        requires_action = (
            urgency_score > 0 or
            '?' in text or
            any(text.startswith(q) for q in ['who', 'what', 'when', 'where', 'why', 'how'])
        )
        
        return {
            'priority': priority,
            'confidence': 0.7,  # Rule-based has moderate confidence
            'requires_action': requires_action,
            'category': 'work' if work_score > 0 else 'personal',
            'classifier_used': 'rule-based',
            'scores': {
                'urgency': urgency_score,
                'work': work_score
            }
        }
    
    async def classify_async(self, message: str) -> Dict[str, Any]:
        """Async wrapper for compatibility."""
        return self.classify(message)