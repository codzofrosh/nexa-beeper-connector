#!/usr/bin/env python3
"""
Simple Interactive Demo - Type messages and see classification results
"""

import requests
import time
import json
import random
import hashlib
import sqlite3

API_URL = "http://localhost:8000"
message_counter = 0
sent_messages = set()  # Track sent messages for duplicate detection

def get_db_status():
    """Get current database status"""
    try:
        conn = sqlite3.connect('data/nexa.db')
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM messages")
        total_msgs = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM messages WHERE classification IS NOT NULL")
        classified = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM actions WHERE status = 'PENDING'")
        pending = cursor.fetchone()[0]
        conn.close()
        return {"total": total_msgs, "classified": classified, "pending": pending}
    except:
        return None

def classify_message(message_text):
    """Send message to API and show results"""
    global message_counter
    message_counter += 1
    
    # Check for local duplicate
    msg_hash = hashlib.md5(message_text.encode()).hexdigest()
    is_duplicate = msg_hash in sent_messages
    sent_messages.add(msg_hash)
    
    try:
        # Use unique ID combining timestamp and random UUID
        message = {
            "id": f"msg_{int(time.time() * 1000)}_{random.randint(10000, 99999)}_{message_counter}",
            "platform": "interactive",
            "sender": "@user:example.com",
            "content": message_text,
            "timestamp": int(time.time()),
        }
        
        response = requests.post(
            f"{API_URL}/api/messages/classify",
            json=message,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # Handle both old and new response formats
            priority = result.get('priority', 'UNKNOWN')
            action_type = result.get('action_type', 'NONE')
            status = result.get('status', 'unknown')
            classification = result.get('classification', {})
            
            # Get classification details
            if isinstance(classification, dict):
                category = classification.get('category', 'UNKNOWN')
                confidence = classification.get('confidence', 0)
                reasoning = classification.get('reasoning', 'N/A')
                requires_action = classification.get('requires_action', False)
            else:
                category = 'UNKNOWN'
                confidence = 0
                reasoning = 'N/A'
                requires_action = False
            
            # Display results simply
            print("--------" * 10)
            print(f"Message: {message_text}")
            if is_duplicate:
                print(f"⚠️  DUPLICATE (sent before in this session)")
            print(f"Priority: {priority.upper()}")
            print(f"Action: {action_type.upper()}")
            print(f"Category: {category.upper()}")
            print(f"Confidence: {confidence:.2%}")
            print(f"Reasoning: {reasoning}")
            print(f"Requires Action: {'YES' if requires_action else 'NO'}")
            print(f"DB Status: {status.upper()}")
            print("--------" * 10)
        else:
            print(f"Error: API returned {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"Error: {e}")

def main():
    """Main loop"""
    print("\nNexa Beeper - Message Classification Demo")
    print("Commands: 'exit' to quit, 'status' for DB info\n")
    
    # Check health
    try:
        response = requests.get(f"{API_URL}/health", timeout=2)
        if response.status_code == 200:
            print("✓ API is running\n")
    except:
        print("✗ API not running!\n")
        return
    
    while True:
        try:
            message = input("> ").strip()
            
            if message.lower() == 'exit':
                break
            
            if message.lower() == 'status':
                db_status = get_db_status()
                if db_status:
                    print(f"\n📊 Database Status:")
                    print(f"  Total messages: {db_status['total']}")
                    print(f"  Classified: {db_status['classified']}")
                    print(f"  Pending actions: {db_status['pending']}\n")
                else:
                    print("Could not read database\n")
                continue
            
            if message:
                classify_message(message)
        
        except KeyboardInterrupt:
            break
    
    print("Goodbye!")

if __name__ == "__main__":
    main()
