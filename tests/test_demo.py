# demo_test.py
"""
Demo script to test the sidecar API
Shows investor how messages are classified and actions are decided
"""

import requests
import json
import time
from datetime import datetime

API_URL = "http://localhost:8000"

def print_section(title):
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def test_health():
    """Test health endpoint"""
    print_section("1. Health Check")
    response = requests.get(f"{API_URL}/health")
    print(json.dumps(response.json(), indent=2))

def set_user_status(status):
    """Set user status"""
    print_section(f"2. Set User Status: {status.upper()}")
    response = requests.post(
        f"{API_URL}/api/user/status",
        json={
            "user_id": "default_user",
            "status": status,
            "auto_reply_message": "I'm currently unavailable. I'll get back to you soon!"
        }
    )
    print(f"✅ Status set to: {status}")

def send_test_message(message_text, platform="demo"):
    """Send a test message for classification"""
    message = {
        "id": f"msg_{int(time.time() * 1000)}",
        "platform": platform,
        "sender": "@user:example.com",
        "content": message_text,
        "timestamp": int(time.time()),
        "metadata": {}
    }
    
    print(f"\n📩 Sending: '{message_text[:50]}...'")
    response = requests.post(
        f"{API_URL}/api/messages/classify",
        json=message
    )
    
    result = response.json()
    if response.status_code != 200:
        print(f"   ERROR Status {response.status_code}: {result}")
        return result
    
    print(f"   Priority: {result['priority']}")
    print(f"   Action: {result['action_type']}")
    print(f"   Confidence: {result['classification']['confidence']:.2f}")
    print(f"   Reasoning: {result['classification']['reasoning']}")
    
    return result

def view_stats():
    """View system statistics"""
    print_section("Statistics")
    response = requests.get(f"{API_URL}/api/stats")
    stats = response.json()
    
    print(f"Total Messages: {stats['total_messages']}")
    print(f"Pending Actions: {stats['pending_actions']}")
    print(f"Classifier: {stats['classifier']}")
    print(f"Ollama Enabled: {stats['ollama_enabled']}")
    print(f"\nPriority Breakdown:")
    for priority, count in stats.get('priority_breakdown', {}).items():
        print(f"  {priority}: {count}")

def view_pending_actions():
    """View pending actions"""
    print_section("Pending Actions")
    response = requests.get(f"{API_URL}/api/actions/pending")
    actions = response.json()['actions']
    
    if not actions:
        print("No pending actions")
    else:
        for action in actions[:5]:  # Show top 5
            print(f"\n  ID: {action['id']}")
            print(f"  Type: {action['action_type']}")
            print(f"  Priority: {action['priority']}")
            print(f"  From: {action['sender']}")
            print(f"  Message: {action['content'][:60]}...")

def run_demo():
    """Run full demo scenario"""
    print("\n" + "="*60)
    print("  NEXA BEEPER CONNECTOR - INVESTOR DEMO")
    print("="*60)
    
    # 1. Health check
    test_health()
    time.sleep(1)
    
    # 2. Scenario: User is AVAILABLE
    print_section("SCENARIO 1: User is AVAILABLE")
    set_user_status("available")
    time.sleep(0.5)
    
    send_test_message("Hey, can we meet tomorrow?")
    send_test_message("Thanks for your help earlier!")
    time.sleep(1)
    
    # 3. Scenario: User switches to DND
    print_section("SCENARIO 2: User switches to DND")
    set_user_status("dnd")
    time.sleep(0.5)
    
    send_test_message("URGENT!!! The production server is down and customers can't access the app!")
    send_test_message("When is the team meeting?")
    send_test_message("Just checking in, hope you're doing well")
    time.sleep(1)
    
    # 4. Scenario: User is BUSY
    print_section("SCENARIO 3: User switches to BUSY")
    set_user_status("busy")
    time.sleep(0.5)
    
    send_test_message("ASAP: Need the quarterly report for client presentation")
    send_test_message("Coffee sometime?")
    time.sleep(1)
    
    # 5. View results
    view_stats()
    time.sleep(0.5)
    view_pending_actions()
    
    print("\n" + "="*60)
    print("  DEMO COMPLETE!")
    print("="*60)
if __name__ == "__main__":
    try:
        run_demo()
    except requests.exceptions.ConnectionError:
        print("\n[ERROR] Cannot connect to API")
        print("Make sure the sidecar is running:")
        print("  python sidecar/main.py")
    except Exception as e:
        print(f"\n[ERROR] {e}")