#!/usr/bin/env python
"""
Interactive demo script to test message classification in real-time
Users can input messages and see priority classification and actions immediately
"""

import requests
import json
import time
from datetime import datetime

API_URL = "http://localhost:8000"

def print_header():
    """Print welcome header"""
    print("\n" + "="*70)
    print("NEXA BEEPER CONNECTOR - INTERACTIVE MESSAGE CLASSIFIER")
    print("="*70)
    print("Type your message and press Enter to classify it")
    print("Commands: 'status', 'stats', 'quit' or 'exit'")
    print("="*70 + "\n")

def check_api_health():
    """Check if API is running"""
    try:
        response = requests.get(f"{API_URL}/health", timeout=2)
        if response.status_code == 200:
            print("[INFO] API is running and healthy")
            return True
    except Exception as e:
        print(f"[ERROR] Cannot connect to API: {e}")
        print(f"[INFO] Make sure sidecar is running: python sidecar/main.py")
        return False

def get_user_status():
    """Get current user status"""
    try:
        response = requests.get(f"{API_URL}/api/user/status?user_id=default_user")
        data = response.json()
        return data.get('status', 'unknown')
    except Exception as e:
        print(f"[ERROR] Failed to get user status: {e}")
        return "unknown"

def set_user_status(status):
    """Set user status"""
    try:
        response = requests.post(
            f"{API_URL}/api/user/status",
            json={
                "user_id": "default_user",
                "status": status,
                "auto_reply_message": f"Currently {status}. Will respond soon!"
            }
        )
        if response.status_code == 200:
            print(f"[OK] User status changed to: {status}")
            return True
    except Exception as e:
        print(f"[ERROR] Failed to set status: {e}")
    return False

def show_stats():
    """Display system statistics"""
    try:
        response = requests.get(f"{API_URL}/api/stats")
        stats = response.json()
        
        print("\n" + "-"*70)
        print("SYSTEM STATISTICS")
        print("-"*70)
        print(f"Total Messages: {stats.get('total_messages', 0)}")
        print(f"Pending Actions: {stats.get('pending_actions', 0)}")
        print(f"Classifier: {stats.get('classifier', 'unknown')}")
        
        if stats.get('ollama_enabled'):
            print(f"Ollama Model: {stats.get('ollama_model', 'N/A')}")
        
        priority_breakdown = stats.get('priority_breakdown', {})
        if priority_breakdown:
            print("\nPriority Breakdown:")
            for priority, count in sorted(priority_breakdown.items()):
                print(f"  {priority.upper()}: {count}")
        print("-"*70 + "\n")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to get stats: {e}")
    return False

def classify_message(text):
    """Send message to classifier and display results"""
    try:
        message = {
            "id": f"msg_{int(time.time() * 1000)}",
            "platform": "interactive",
            "sender": "@user:interactive",
            "content": text,
            "timestamp": int(time.time()),
            "metadata": {}
        }
        
        response = requests.post(
            f"{API_URL}/api/messages/classify",
            json=message,
            timeout=10
        )
        
        if response.status_code != 200:
            print(f"[ERROR] API returned status {response.status_code}")
            print(f"[ERROR] Response: {response.text}")
            return False
        
        result = response.json()
        
        # Display results
        print("\n" + "-"*70)
        print("CLASSIFICATION RESULT")
        print("-"*70)
        print(f"Message: {text[:60]}{'...' if len(text) > 60 else ''}")
        print(f"Priority: {result.get('priority', 'N/A').upper()}")
        print(f"Action: {result.get('action_type', 'N/A').upper()}")
        
        classification = result.get('classification', {})
        print(f"Category: {classification.get('category', 'N/A').upper()}")
        print(f"Confidence: {classification.get('confidence', 0):.2%}")
        print(f"Reasoning: {classification.get('reasoning', 'N/A')}")
        print(f"Requires Action: {'YES' if classification.get('requires_action') else 'NO'}")
        print("-"*70 + "\n")
        
        return True
        
    except requests.exceptions.Timeout:
        print("[ERROR] Request timed out. The API may be busy or offline.")
        return False
    except Exception as e:
        print(f"[ERROR] Failed to classify message: {e}")
        return False

def show_commands():
    """Show available commands"""
    print("\nAvailable commands:")
    print("  'status'     - Show current user status")
    print("  'available'  - Set status to available")
    print("  'busy'       - Set status to busy")
    print("  'dnd'        - Set status to do-not-disturb")
    print("  'stats'      - Show system statistics")
    print("  'help'       - Show this help message")
    print("  'quit/exit'  - Exit the program")
    print()

def main():
    """Main interactive loop"""
    print_header()
    
    # Check if API is available
    if not check_api_health():
        print("\n[FATAL] Cannot connect to API. Exiting.")
        return
    
    print(f"[OK] Current user status: {get_user_status()}\n")
    
    try:
        while True:
            try:
                user_input = input("> ").strip()
                
                if not user_input:
                    continue
                
                # Handle commands
                if user_input.lower() in ['quit', 'exit']:
                    print("\nGoodbye!")
                    break
                
                elif user_input.lower() == 'status':
                    status = get_user_status()
                    print(f"[INFO] Current status: {status}")
                
                elif user_input.lower() == 'available':
                    set_user_status('available')
                
                elif user_input.lower() == 'busy':
                    set_user_status('busy')
                
                elif user_input.lower() == 'dnd':
                    set_user_status('dnd')
                
                elif user_input.lower() == 'stats':
                    show_stats()
                
                elif user_input.lower() in ['help', '?']:
                    show_commands()
                
                else:
                    # Treat as message to classify
                    classify_message(user_input)
            
            except KeyboardInterrupt:
                print("\n\n[INFO] Interrupted by user")
                break
            except Exception as e:
                print(f"[ERROR] Unexpected error: {e}")
    
    finally:
        print("\n[INFO] Interactive session ended")

if __name__ == "__main__":
    main()
