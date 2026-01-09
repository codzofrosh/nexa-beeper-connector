#!/usr/bin/env bash
set -e

BASE="http://localhost:8080"

# Wait for server to become available (timeout after ~15s)
for i in {1..15}; do
  if curl -s "$BASE/actions" >/dev/null 2>&1; then
    echo "Server is up"
    break
  fi
  echo "Waiting for server to start... ($i)"
  sleep 1
done

echo "==============================="
echo "TEST 1 — Clean start"
echo "==============================="

curl -s "$BASE/actions" || true
echo -e "\n(Expect empty list)\n"

sleep 1

echo "==============================="
echo "TEST 2 — First message"
echo "==============================="

curl -X POST "$BASE/message" \
  -H "Content-Type: application/json" \
  --data-raw '{
    "platform":"whatsapp",
    "room_id":"r1",
    "sender":"+91",
    "sender_name":"Tester",
    "is_group":false,
    "timestamp":123,
    "text":"price please",
    "message_id":"msg-001"
  }'

sleep 1
curl "$BASE/actions"
echo -e "\n(Expect 1 action)\n"

echo "==============================="
echo "TEST 3 — Duplicate message"
echo "==============================="

curl -X POST "$BASE/message" \
  -H "Content-Type: application/json" \
  --data-raw '{
    "platform":"whatsapp",
    "room_id":"r1",
    "sender":"+91",
    "sender_name":"Tester",
    "is_group":false,
    "timestamp":123,
    "text":"price please",
    "message_id":"msg-001"
  }'

sleep 1
curl "$BASE/actions"
echo -e "\n(Still expect only 1 action)\n"

echo "==============================="
echo "TEST 4 — New message"
echo "==============================="

curl -X POST "$BASE/message" \
  -H "Content-Type: application/json" \
  --data-raw '{
    "platform":"whatsapp",
    "room_id":"r1",
    "sender":"+92",
    "sender_name":"Tester2",
    "is_group":false,
    "timestamp":124,
    "text":"price",
    "message_id":"msg-002"
  }'

sleep 1
curl "$BASE/actions"
echo -e "\n(Expect 2 actions total)\n"

echo "==============================="
echo "TEST 5 — Restart executor"
echo "==============================="
echo ">>> Manually restart executor NOW"
read -p "Press ENTER after restart..."

curl "$BASE/actions"
echo -e "\n(Expect SAME actions, no new ones)\n"

echo "==============================="
echo "TEST 6 — Replay protection"
echo "==============================="

curl -X POST "$BASE/message" \
  -H "Content-Type: application/json" \
  --data-raw '{
    "platform":"whatsapp",
    "room_id":"r1",
    "sender":"+91",
    "sender_name":"Tester",
    "is_group":false,
    "timestamp":125,
    "text":"price please",
    "message_id":"msg-001"
  }'

sleep 1
curl "$BASE/actions"
echo -e "\n(Expect NO change)\n"

echo "==============================="
echo "TEST 7 — Crash mid-execution"
echo "==============================="
echo ">>> Send message, then KILL executor immediately"

curl -X POST "$BASE/message" \
  -H "Content-Type: application/json" \
  --data-raw '{
    "platform":"whatsapp",
    "room_id":"r1",
    "sender":"+93",
    "sender_name":"CrashTest",
    "is_group":false,
    "timestamp":126,
    "text":"price please",
    "message_id":"msg-CRASH"
  }'

echo ">>> Kill executor NOW"
read -p "Press ENTER after killing executor..."

echo ">>> Restart executor"
read -p "Press ENTER after restart..."

sleep 1
curl "$BASE/actions"
echo -e "\n(Expect msg-CRASH exactly once)\n"

echo "==============================="
echo "ALL TESTS COMPLETED"
echo "==============================="
