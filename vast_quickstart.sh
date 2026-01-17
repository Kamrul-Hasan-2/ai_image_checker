#!/bin/bash
# Quick Start Script for Vast.ai
# Run this after SSHing into your Vast.ai instance

echo "=========================================="
echo "Vast.ai AI Image Checker - Quick Setup"
echo "=========================================="
echo ""

# Check if we're in the right directory
if [ ! -d "/opt/ai_image_checker" ]; then
    echo "❌ Directory /opt/ai_image_checker not found!"
    echo "Please transfer your files first."
    exit 1
fi

cd /opt/ai_image_checker

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Check if fastapi is installed
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "📥 Installing dependencies..."
    echo "This may take a few minutes..."
    
    # Try with trusted hosts to bypass SSL issues
    pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org \
        fastapi uvicorn python-multipart pillow requests
    
    if [ $? -ne 0 ]; then
        echo "❌ Installation failed. Check your internet connection."
        exit 1
    fi
else
    echo "✅ Dependencies already installed"
fi

# Check if main.py exists
if [ ! -f "main.py" ]; then
    echo "❌ main.py not found!"
    exit 1
fi

echo ""
echo "=========================================="
echo "🚀 Starting AI Image Checker Service"
echo "=========================================="
echo ""
echo "Service will be available at:"
echo "  📍 Local:  http://localhost:8000"
echo "  🌐 Public: http://$(curl -s ifconfig.me):8000"
echo "  📚 Docs:   http://$(curl -s ifconfig.me):8000/docs"
echo ""
echo "Press Ctrl+C to stop the service"
echo "Or use screen to run in background:"
echo "  screen -S api && python3 main.py"
echo "=========================================="
echo ""

# Start the service
python3 main.py
