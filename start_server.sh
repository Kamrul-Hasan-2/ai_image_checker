#!/bin/bash
# Vast AI Server Startup Script

cd ~/ai_image_checker

echo "Installing dependencies..."
pip install -q 'accelerate>=0.26.0'

echo "Starting AI Image Checker Server..."
nohup python main.py --host 0.0.0.0 --port 8000 > server.log 2>&1 &

echo "Server started! PID: $!"
sleep 5

echo "Checking server status..."
curl http://localhost:8000/health

echo ""
echo "Server logs: tail -f ~/ai_image_checker/server.log"
echo "Stop server: pkill -f main.py"
