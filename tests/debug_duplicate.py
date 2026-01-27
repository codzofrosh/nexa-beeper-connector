#!/usr/bin/env python3
"""Debug duplicate detection"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sidecar.database import DatabaseService
import hashlib
import time

db = DatabaseService()

# Test 1: Store a message
msg_id_1 = hashlib.md5(f"hello_{int(time.time())}".encode()).hexdigest()[:16]
print(f"Test 1 - Store first message")
print(f"  Message ID: {msg_id_1}")

success = db.store_message(
    message_id=msg_id_1,
    platform="test",
    sender="@user",
    content="hello",
    timestamp=int(time.time())
)
print(f"  Stored: {success}")

# Test 2: Check if it exists
exists = db.message_exists(msg_id_1)
print(f"\nTest 2 - Check if message exists")
print(f"  Message ID: {msg_id_1}")
print(f"  Exists: {exists}")

# Test 3: Try to store same ID again (should fail)
print(f"\nTest 3 - Try to store duplicate")
success = db.store_message(
    message_id=msg_id_1,
    platform="test",
    sender="@user",
    content="hello",
    timestamp=int(time.time())
)
print(f"  Stored: {success}")

# Test 4: Check database directly
print(f"\nTest 4 - Check database")
import sqlite3
conn = sqlite3.connect('data/nexa.db')
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM messages")
count = cursor.fetchone()[0]
print(f"  Total messages: {count}")
cursor.execute("SELECT id, content FROM messages")
for row in cursor.fetchall():
    print(f"    {row[0]}: {row[1]}")
conn.close()
