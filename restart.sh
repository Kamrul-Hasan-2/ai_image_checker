#!/bin/bash
# Simple server restart script for Linux (no systemd)

echo "🔄 Restarting AI Image Checker Server..."
echo "=========================================="

# Kill existing Python process on port 8000
echo "Stopping existing server..."
PID=$(lsof -ti:8000 2>/dev/null)
if [ ! -z "$PID" ]; then
    kill -9 $PID 2>/dev/null
    echo "✅ Killed process $PID"
    sleep 2
else
    echo "⚠️  No existing server found"
fi

# Start server in background
echo "Starting server..."
cd ~/ai_image_checker
nohup python3 main.py --port 8000 > server.log 2>&1 &
NEW_PID=$!
echo "✅ Server started with PID: $NEW_PID"

sleep 3

# Test if server is running
echo ""
echo "Testing server..."
if curl -s http://localhost:8000/image_checker/health | grep -q "healthy"; then
    echo "✅ Server is running successfully!"
    echo ""
    echo "Your endpoints:"
    echo "  LOCAL:  http://localhost:8000/image_checker/health"
    echo "  PUBLIC: https://ais.bdstall.com/image_checker/health"
else
    echo "❌ Server failed to start. Check logs:"
    echo "   tail -f ~/ai_image_checker/server.log"
fi

echo ""
echo "To see logs: tail -f ~/ai_image_checker/server.log"
