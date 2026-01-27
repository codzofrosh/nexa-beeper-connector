# ai/local_model.py

"""
Local on-device AI classifier using TensorFlow Lite.
Optimized for mobile deployment with minimal battery impact.
"""

import logging
import numpy as np
from typing import Dict, Any, Optional
import os

logger = logging.getLogger(__name__)

# Try to import TensorFlow Lite
try:
    import tensorflow as tf
    HAS_TFLITE = True
except ImportError:
    HAS_TFLITE = False
    logger.warning("TensorFlow Lite not available. Install with: pip install tensorflow")


class LocalClassifier:
    """
    On-device message classifier using TensorFlow Lite.
    Falls back to basic heuristics if model not available.
    """
    
    def __init__(self, model_path: str = "ai/models/message_classifier.tflite"):
        self.model_path = model_path
        self.interpreter = None
        self.input_details = None
        self.output_details = None
        self.vocab = None
        self.max_length = 128
        
        # Priority labels (must match training order)
        self.priority_labels = ['low', 'normal', 'high', 'urgent']
        
        # Category labels
        self.category_labels = ['personal', 'work', 'marketing', 'social']
        
        # Try to load the model
        if HAS_TFLITE and os.path.exists(model_path):
            self._load_model()
        else:
            logger.warning(f"Model not found at {model_path}. Using fallback classification.")
    
    def _load_model(self):
        """Load TensorFlow Lite model."""
        try:
            self.interpreter = tf.lite.Interpreter(model_path=self.model_path)
            self.interpreter.allocate_tensors()
            
            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()
            
            # Load vocabulary if exists
            vocab_path = self.model_path.replace('.tflite', '_vocab.txt')
            if os.path.exists(vocab_path):
                self.vocab = self._load_vocab(vocab_path)
            
            logger.info(f"✅ Loaded TFLite model from {self.model_path}")
            
        except Exception as e:
            logger.error(f"Failed to load TFLite model: {e}")
            self.interpreter = None
    
    def _load_vocab(self, vocab_path: str) -> Dict[str, int]:
        """Load vocabulary mapping."""
        vocab = {}
        with open(vocab_path, 'r', encoding='utf-8') as f:
            for idx, word in enumerate(f):
                vocab[word.strip()] = idx
        return vocab
    
    def classify(self, message: str) -> Dict[str, Any]:
        """
        Classify message using TFLite model or fallback.
        
        Args:
            message: Text message to classify
            
        Returns:
            Classification result with priority, confidence, etc.
        """
        if self.interpreter is not None:
            return self._classify_with_model(message)
        else:
            return self._classify_fallback(message)
    
    async def classify_async(self, message: str) -> Dict[str, Any]:
        """Async wrapper for compatibility."""
        return self.classify(message)
    
    def _classify_with_model(self, message: str) -> Dict[str, Any]:
        """Classify using TFLite model."""
        try:
            # Preprocess text
            input_data = self._preprocess(message)
            
            # Set input tensor
            self.interpreter.set_tensor(
                self.input_details[0]['index'],
                input_data
            )
            
            # Run inference
            self.interpreter.invoke()
            
            # Get outputs
            # Assuming model outputs: [priority_logits, category_logits]
            priority_output = self.interpreter.get_tensor(
                self.output_details[0]['index']
            )[0]
            
            # Apply softmax to get probabilities
            priority_probs = self._softmax(priority_output)
            
            # Get predicted class
            priority_idx = np.argmax(priority_probs)
            priority = self.priority_labels[priority_idx]
            confidence = float(priority_probs[priority_idx])
            
            # If model has category output (multi-output model)
            category = 'personal'
            if len(self.output_details) > 1:
                category_output = self.interpreter.get_tensor(
                    self.output_details[1]['index']
                )[0]
                category_probs = self._softmax(category_output)
                category_idx = np.argmax(category_probs)
                category = self.category_labels[category_idx]
            
            return {
                'priority': priority,
                'confidence': confidence,
                'category': category,
                'requires_action': priority in ['high', 'urgent'],
                'classifier_used': 'local-tflite',
                'probabilities': {
                    label: float(prob)
                    for label, prob in zip(self.priority_labels, priority_probs)
                }
            }
            
        except Exception as e:
            logger.error(f"Model inference failed: {e}")
            return self._classify_fallback(message)
    
    def _preprocess(self, message: str) -> np.ndarray:
        """
        Preprocess text for model input.
        
        Simple tokenization approach:
        - Convert to lowercase
        - Split into words
        - Convert to IDs using vocabulary
        - Pad/truncate to max_length
        """
        message = message.lower()
        words = message.split()
        
        # Convert words to IDs
        if self.vocab:
            # Use vocabulary
            ids = [
                self.vocab.get(word, self.vocab.get('<UNK>', 0))
                for word in words
            ]
        else:
            # Simple hash-based encoding (not ideal but works)
            ids = [hash(word) % 10000 for word in words]
        
        # Pad or truncate
        if len(ids) < self.max_length:
            ids = ids + [0] * (self.max_length - len(ids))
        else:
            ids = ids[:self.max_length]
        
        # Convert to numpy array with correct shape
        input_array = np.array([ids], dtype=np.float32)
        
        return input_array
    
    def _softmax(self, x: np.ndarray) -> np.ndarray:
        """Apply softmax to get probabilities."""
        exp_x = np.exp(x - np.max(x))
        return exp_x / exp_x.sum()
    
    def _classify_fallback(self, message: str) -> Dict[str, Any]:
        """
        Fallback classification when model is not available.
        Uses simple keyword matching.
        """
        text = message.lower()
        
        # Keyword-based classification
        urgent_keywords = ['urgent', 'asap', 'emergency', 'critical', 'help', '!!!']
        high_keywords = ['important', 'deadline', 'meeting', 'client', 'review']
        
        urgent_count = sum(1 for kw in urgent_keywords if kw in text)
        high_count = sum(1 for kw in high_keywords if kw in text)
        
        if urgent_count >= 1:
            priority = 'urgent'
            confidence = 0.6
        elif high_count >= 1:
            priority = 'high'
            confidence = 0.6
        elif '?' in text:
            priority = 'normal'
            confidence = 0.5
        else:
            priority = 'low'
            confidence = 0.5
        
        return {
            'priority': priority,
            'confidence': confidence,
            'category': 'personal',
            'requires_action': priority in ['high', 'urgent'],
            'classifier_used': 'local-fallback'
        }


# Helper function to create a simple model (for development/testing)
def create_simple_tflite_model(save_path: str = "ai/models/message_classifier.tflite"):
    """
    Create a simple TFLite model for testing.
    This is a placeholder - you'd train a real model on your data.
    """
    if not HAS_TFLITE:
        logger.error("TensorFlow not available")
        return
    
    import tensorflow as tf
    from tensorflow import keras
    
    # Create a simple model
    model = keras.Sequential([
        keras.layers.Input(shape=(128,)),
        keras.layers.Embedding(10000, 64),
        keras.layers.GlobalAveragePooling1D(),
        keras.layers.Dense(32, activation='relu'),
        keras.layers.Dropout(0.3),
        keras.layers.Dense(4, activation='softmax')  # 4 priority classes
    ])
    
    model.compile(
        optimizer='adam',
        loss='sparse_categorical_crossentropy',
        metrics=['accuracy']
    )
    
    # Convert to TFLite
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    tflite_model = converter.convert()
    
    # Save
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    with open(save_path, 'wb') as f:
        f.write(tflite_model)
    
    logger.info(f"✅ Created simple TFLite model at {save_path}")
    
    # Create vocab file
    vocab_path = save_path.replace('.tflite', '_vocab.txt')
    common_words = ['urgent', 'help', 'meeting', 'important', 'deadline', 
                    'please', 'thanks', 'hello', 'question', 'asap']
    with open(vocab_path, 'w') as f:
        f.write('<PAD>\n<UNK>\n')
        for word in common_words:
            f.write(f'{word}\n')
    
    logger.info(f"✅ Created vocabulary at {vocab_path}")


if __name__ == "__main__":
    # Test the classifier
    print("Testing LocalClassifier...")
    
    # Optionally create a simple model for testing
    # create_simple_tflite_model()
    
    classifier = LocalClassifier()
    
    test_messages = [
        "URGENT: Server is down!!!",
        "Can we schedule a meeting?",
        "Thanks for your help",
        "ASAP - Need files for client presentation",
    ]
    
    for msg in test_messages:
        result = classifier.classify(msg)
        print(f"\nMessage: {msg}")
        print(f"Priority: {result['priority']} (confidence: {result['confidence']:.2f})")
        print(f"Classifier: {result['classifier_used']}")