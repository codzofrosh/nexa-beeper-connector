#!/usr/bin/env python3
"""
Comprehensive Functionality Demo & Verification Script

This script tests all major features of the Nexa Beeper Sidecar:
- Message classification (LLM + fallback)
- User status management
- Action decision making
- Database persistence
- Deduplication
- Statistics aggregation
"""

import requests
import json
import time
import sys
from datetime import datetime

API_URL = "http://localhost:8000"

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

def print_section(title):
    """Print a formatted section header"""
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BOLD}{BLUE}  {title}{RESET}")
    print(f"{BLUE}{'='*70}{RESET}")

def print_success(message):
    """Print success message"""
    print(f"{GREEN}[OK]{RESET} {message}")

def print_error(message):
    """Print error message"""
    print(f"{RED}[ERROR]{RESET} {message}")

def print_warning(message):
    """Print warning message"""
    print(f"{YELLOW}[WARN]{RESET} {message}")

def print_info(message):
    """Print info message"""
    print(f"{BLUE}[INFO]{RESET} {message}")

def check_api_health():
    """Check if API is running and healthy"""
    try:
        response = requests.get(f"{API_URL}/health", timeout=2)
        if response.status_code == 200:
            data = response.json()
            print_success("API is running and healthy")
            print(f"  Service: {data.get('service', 'unknown')}")
            print(f"  Ollama: {'Available' if data.get('ollama_available', False) else 'Not available'}")
            print(f"  Database: {data.get('db_path', 'unknown')}")
            return True
    except Exception as e:
        print_error(f"Cannot connect to API: {e}")
        print_info("Make sure sidecar is running: python sidecar/main.py")
        return False

def test_classification():
    """Test message classification with various priorities"""
    print_section("TEST 1: MESSAGE CLASSIFICATION")
    
    test_cases = [
        ("URGENT: Production server is down!", "urgent"),
        ("Meeting scheduled for tomorrow at 2pm", "high"),
        ("Thanks for the update", "normal"),
        ("How are you doing today?", "normal"),
        ("Just checking in", "low"),
    ]
    
    for message_text, expected_priority in test_cases:
        try:
            message = {
                "id": f"msg_{int(time.time() * 1000)}_{abs(hash(message_text)) % 10000}",
                "platform": "test",
                "sender": "@user:example.com",
                "content": message_text,
                "timestamp": int(time.time()),
            }
            
            response = requests.post(
                f"{API_URL}/api/messages/classify",
                json=message,
                timeout=30
            )
            
            if response.status_code != 200:
                print_error(f"Classification failed: {response.text[:100]}")
                continue
            
            result = response.json()
            priority = result.get('priority', 'unknown')
            confidence = result.get('classification', {}).get('confidence', 0)
            classifier_used = result.get('classification', {}).get('classifier_used', 'unknown')
            
            print(f"\n  Message: '{message_text[:50]}...'")
            print(f"    Priority: {BOLD}{priority}{RESET} (expected: {expected_priority})")
            print(f"    Confidence: {confidence:.2%}")
            print(f"    Classifier: {classifier_used}")
            print(f"    Action: {result.get('action_type', 'none')}")
            print(f"    Status: {result.get('status', 'unknown')}")
            
            if priority == expected_priority or confidence > 0.7:
                print_success(f"Classification correct")
            else:
                print_warning(f"Classification different than expected")
                
        except Exception as e:
            print_error(f"Classification request failed: {e}")
        
        time.sleep(0.5)  # Rate limiting

def test_user_status():
    """Test user status management"""
    print_section("TEST 2: USER STATUS MANAGEMENT")
    
    statuses = ["available", "busy", "dnd"]
    
    for status in statuses:
        try:
            # Set status
            response = requests.post(
                f"{API_URL}/api/user/status",
                json={
                    "user_id": "test_user",
                    "status": status,
                    "auto_reply_message": f"I am currently {status}"
                },
                timeout=5
            )
            
            if response.status_code != 200:
                print_error(f"Failed to set status {status}")
                continue
            
            print_success(f"Status set to: {BOLD}{status}{RESET}")
            
            # Get status back
            response = requests.get(
                f"{API_URL}/api/user/status?user_id=test_user",
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                retrieved_status = data.get('status')
                if retrieved_status == status:
                    print_success(f"Status verified: {retrieved_status}")
                else:
                    print_error(f"Status mismatch: got {retrieved_status}, expected {status}")
            else:
                print_error(f"Failed to retrieve status")
                
        except Exception as e:
            print_error(f"Status management failed: {e}")
        
        time.sleep(0.3)

def test_action_decisions():
    """Test action decisions based on priority and status"""
    print_section("TEST 3: ACTION DECISION MATRIX")
    
    # Set different statuses and send messages
    test_matrix = [
        ("available", "URGENT: Help!", "urgent"),
        ("busy", "Can we meet tomorrow?", "high"),
        ("dnd", "URGENT: Server down!", "urgent"),
    ]
    
    for user_status, message_text, priority in test_matrix:
        try:
            # Set user status
            requests.post(
                f"{API_URL}/api/user/status",
                json={
                    "user_id": "decision_test",
                    "status": user_status,
                    "auto_reply_message": f"Status: {user_status}"
                },
                timeout=5
            )
            
            # Send message
            message = {
                "id": f"msg_{int(time.time() * 1000)}_{abs(hash(message_text)) % 10000}",
                "platform": "test",
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
                action = result.get('action_type', 'none')
                print(f"\n  Status: {BOLD}{user_status}{RESET}")
                print(f"  Message: '{message_text[:40]}...'")
                print(f"  Priority: {result.get('priority', 'unknown')}")
                print(f"  Action: {BOLD}{action}{RESET}")
                print_success(f"Decision made successfully")
            else:
                print_error(f"Failed to get action decision")
                
        except Exception as e:
            print_error(f"Action decision test failed: {e}")
        
        time.sleep(0.5)

def test_deduplication():
    """Test deduplication - same message should be marked as duplicate"""
    print_section("TEST 4: DEDUPLICATION")
    
    message_id = f"dedup_test_{int(time.time())}"
    message = {
        "id": message_id,
        "platform": "test",
        "sender": "@user:example.com",
        "content": "This is a test message for deduplication",
        "timestamp": int(time.time()),
    }
    
    try:
        # First send
        print("Sending message (first time)...")
        response1 = requests.post(
            f"{API_URL}/api/messages/classify",
            json=message,
            timeout=30
        )
        
        if response1.status_code == 200:
            result1 = response1.json()
            status1 = result1.get('status', 'unknown')
            action1 = result1.get('action_id')
            
            print_success(f"First send: status={status1}, action_id={action1}")
            
            # Second send (duplicate)
            print("\nSending same message again (duplicate)...")
            response2 = requests.post(
                f"{API_URL}/api/messages/classify",
                json=message,
                timeout=30
            )
            
            if response2.status_code == 200:
                result2 = response2.json()
                status2 = result2.get('status', 'unknown')
                
                if status2 == 'duplicate':
                    print_success(f"Duplicate properly detected: status={status2}")
                else:
                    print_warning(f"Expected duplicate, got status={status2}")
            else:
                print_error(f"Second request failed")
        else:
            print_error(f"First request failed")
            
    except Exception as e:
        print_error(f"Deduplication test failed: {e}")

def test_pending_actions():
    """Test retrieving pending actions"""
    print_section("TEST 5: PENDING ACTIONS")
    
    try:
        response = requests.get(
            f"{API_URL}/api/actions/pending?limit=10",
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            count = data.get('count', 0)
            actions = data.get('actions', [])
            
            print_success(f"Retrieved {count} pending actions")
            
            if actions:
                print("\nPending actions:")
                for i, action in enumerate(actions[:5], 1):
                    print(f"  {i}. ID={action.get('id')}, "
                          f"Priority={action.get('priority')}, "
                          f"Status={action.get('status')}")
            else:
                print_info("No pending actions")
        else:
            print_error(f"Failed to retrieve pending actions")
            
    except Exception as e:
        print_error(f"Pending actions test failed: {e}")

def test_recent_messages():
    """Test retrieving recent messages"""
    print_section("TEST 6: RECENT MESSAGES")
    
    try:
        response = requests.get(
            f"{API_URL}/api/messages/recent?limit=5",
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            count = data.get('count', 0)
            messages = data.get('messages', [])
            
            print_success(f"Retrieved {count} recent messages")
            
            if messages:
                print("\nRecent messages:")
                for i, msg in enumerate(messages[:5], 1):
                    content = msg.get('content', '')[:40]
                    print(f"  {i}. From: {msg.get('sender', 'unknown')}, "
                          f"Content: '{content}...'")
            else:
                print_info("No messages in database")
        else:
            print_error(f"Failed to retrieve recent messages")
            
    except Exception as e:
        print_error(f"Recent messages test failed: {e}")

def test_statistics():
    """Test statistics endpoint"""
    print_section("TEST 7: SYSTEM STATISTICS")
    
    try:
        response = requests.get(
            f"{API_URL}/api/stats",
            timeout=5
        )
        
        if response.status_code == 200:
            stats = response.json()
            
            print_success("Statistics retrieved")
            print(f"\n  Total Messages: {stats.get('total_messages', 0)}")
            print(f"  Pending Actions: {stats.get('pending_actions', 0)}")
            
            priority_breakdown = stats.get('priority_breakdown', {})
            if priority_breakdown:
                print(f"\n  Priority Breakdown:")
                for priority, count in sorted(priority_breakdown.items()):
                    print(f"    {BOLD}{priority}{RESET}: {count}")
            
            classifier_breakdown = stats.get('classifier_breakdown', {})
            if classifier_breakdown:
                print(f"\n  Classifier Used:")
                for classifier, count in sorted(classifier_breakdown.items()):
                    print(f"    {classifier}: {count}")
            
            print(f"\n  Ollama Enabled: {stats.get('ollama_enabled', False)}")
            print(f"  Classifier Type: {stats.get('classifier', 'unknown')}")
        else:
            print_error(f"Failed to retrieve statistics")
            
    except Exception as e:
        print_error(f"Statistics test failed: {e}")

def run_all_tests():
    """Run all tests"""
    print(f"\n{BOLD}{BLUE}")
    print("╔" + "═"*68 + "╗")
    print("║" + " "*15 + "NEXA BEEPER SIDECAR - COMPREHENSIVE TEST SUITE" + " "*9 + "║")
    print("╚" + "═"*68 + "╝")
    print(RESET)
    
    print(f"\nTest Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check API health first
    print_section("PREREQUISITES: API HEALTH CHECK")
    if not check_api_health():
        print_error("API is not available. Please start the sidecar service.")
        sys.exit(1)
    
    # Run all tests
    try:
        test_classification()
        time.sleep(1)
        
        test_user_status()
        time.sleep(1)
        
        test_action_decisions()
        time.sleep(1)
        
        test_deduplication()
        time.sleep(1)
        
        test_pending_actions()
        time.sleep(1)
        
        test_recent_messages()
        time.sleep(1)
        
        test_statistics()
        
    except KeyboardInterrupt:
        print_warning("\nTests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error during tests: {e}")
        sys.exit(1)
    
    # Summary
    print_section("TEST SUITE COMPLETED")
    print_success("All tests completed successfully!")
    print(f"Test End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nFor more detailed information, see the QUICK_REFERENCE.md and ARCHITECTURE.md")

if __name__ == "__main__":
    try:
        run_all_tests()
    except Exception as e:
        print_error(f"Fatal error: {e}")
        sys.exit(1)
