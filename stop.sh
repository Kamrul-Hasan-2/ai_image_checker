#!/bin/bash
# Stop the AI Image Checker server

echo "Stopping AI Image Checker Server..."

PID=$(lsof -ti:8000 2>/dev/null)
if [ ! -z "$PID" ]; then
    kill -9 $PID
    echo "✅ Server stopped (PID: $PID)"
else
    echo "⚠️  No server running on port 8000"
fi
