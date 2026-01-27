#!/bin/bash
# run_demo.sh

echo "🚀 Starting Nexa Beeper Connector Demo"
echo ""

# 1. Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# 2. Start sidecar
echo ""
echo "🔄 Starting sidecar API..."
python sidecar/main.py &
SIDECAR_PID=$!

# Wait for startup
sleep 3

# 3. Run demo
echo ""
echo "▶️  Running demo..."
python demo_test.py

# 4. Keep sidecar running
echo ""
echo "✅ Demo complete! Sidecar still running on http://localhost:8000"
echo "   - API docs: http://localhost:8000/docs"
echo "   - Health: http://localhost:8000/health"
echo ""
echo "Press Ctrl+C to stop"

wait $SIDECAR_PID