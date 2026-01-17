#!/bin/bash
# Start Service Script for Vast.ai
# Run this after setup: bash start_vast_ai.sh

APP_DIR="/workspace/ai_image_checker"

if [ ! -d "$APP_DIR" ]; then
    echo "❌ App directory not found: $APP_DIR"
    echo "Please run setup_vast_ai.sh first"
    exit 1
fi

cd "$APP_DIR"

if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found"
    echo "Please run setup_vast_ai.sh first"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

echo "=========================================="
echo "🚀 Starting AI Image Checker Service"
echo "=========================================="
echo ""
echo "📍 Service will be available at:"
echo "   Local:  http://localhost:8000"
echo "   Public: http://$(curl -s ifconfig.me):8000"
echo "   Docs:   http://$(curl -s ifconfig.me):8000/docs"
echo ""
echo "Press Ctrl+C to stop"
echo "=========================================="
echo ""

# Start the service
python3 main.py
