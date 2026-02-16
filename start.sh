#!/bin/bash
# Start the AI Image Checker server

cd ~/ai_image_checker

echo "🚀 Starting AI Image Checker Server..."
nohup python3 main.py --port 8000 > server.log 2>&1 &
PID=$!
echo "✅ Server started with PID: $PID"
echo ""
echo "Monitor logs: tail -f ~/ai_image_checker/server.log"
echo "Test endpoint: curl http://localhost:8000/image_checker/health"
