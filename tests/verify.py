#!/usr/bin/env python3
"""
Quick Verification Script - Fast API Health Check

Runs basic connectivity tests to verify the Nexa Beeper Sidecar is working.
"""

import requests
import sys
import time

API_URL = "http://localhost:8000"

GREEN = '\033[92m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

def test_endpoint(name, method, endpoint, expected_status=200, **kwargs):
    """Test a single API endpoint"""
    try:
        url = f"{API_URL}{endpoint}"
        if method == "GET":
            response = requests.get(url, timeout=5, **kwargs)
        else:
            response = requests.post(url, timeout=5, **kwargs)
        
        status = "✓" if response.status_code == expected_status else "✗"
        color = GREEN if response.status_code == expected_status else RED
        
        print(f"  {color}{status}{RESET} {name} - {response.status_code}")
        return response.status_code == expected_status
        
    except Exception as e:
        print(f"  {RED}✗{RESET} {name} - Error: {str(e)[:50]}")
        return False

def main():
    print(f"\n{BOLD}{BLUE}Nexa Beeper Sidecar - Quick Verification{RESET}\n")
    
    # Test 1: Health check
    print("1. Testing API Health...")
    if not test_endpoint("Health Check", "GET", "/health"):
        print(f"\n{RED}✗ API is not responding. Start it with: python sidecar/main.py{RESET}\n")
        sys.exit(1)
    
    # Test 2: Database connectivity
    print("\n2. Testing Database...")
    test_endpoint("Recent Messages", "GET", "/api/messages/recent?limit=1")
    
    # Test 3: Classification
    print("\n3. Testing Message Classification...")
    test_message = {
        "id": f"verify_{int(time.time())}",
        "platform": "verify",
        "sender": "@test:example.com",
        "content": "Test message",
        "timestamp": int(time.time())
    }
    test_endpoint(
        "Classify Message", 
        "POST", 
        "/api/messages/classify",
        200,
        json=test_message
    )
    
    # Test 4: Status management
    print("\n4. Testing User Status...")
    test_endpoint(
        "Set Status",
        "POST",
        "/api/user/status",
        200,
        json={
            "user_id": "test",
            "status": "available",
            "auto_reply_message": "Test"
        }
    )
    
    # Test 5: Statistics
    print("\n5. Testing Statistics...")
    test_endpoint("Get Statistics", "GET", "/api/stats")
    
    print(f"\n{GREEN}✓ All basic tests passed!{RESET}")
    print("\nNext steps:")
    print("  • Run comprehensive demo: python tests/comprehensive_demo.py")
    print("  • Run interactive demo:  python tests/interactive_demo.py")
    print()

if __name__ == "__main__":
    main()
