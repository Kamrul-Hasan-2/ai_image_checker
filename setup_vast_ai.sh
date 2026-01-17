#!/bin/bash
# Complete Setup Script for Vast.ai
# Run this on your Vast.ai server: bash setup_vast_ai.sh

set -e  # Exit on error

echo "=========================================="
echo "🚀 Vast.ai AI Image Checker Setup"
echo "=========================================="
echo ""

# Update system
echo "📦 Updating system packages..."
apt-get update -qq

# Install required system packages
echo "📦 Installing system dependencies..."
apt-get install -y --no-install-recommends \
    python3-pip \
    python3-venv \
    libgl1-mesa-glx \
    libglib2.0-0 \
    wget \
    curl \
    screen

# Create app directory if it doesn't exist
APP_DIR="/workspace/ai_image_checker"
if [ ! -d "$APP_DIR" ]; then
    mkdir -p "$APP_DIR"
fi

cd "$APP_DIR"

# Create virtual environment
echo "🔧 Creating Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip setuptools wheel

# Install dependencies
echo "📥 Installing Python dependencies..."
echo "This may take 5-10 minutes..."

# Install PyTorch first (for GPU support)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Install other dependencies
pip install \
    fastapi==0.115.6 \
    uvicorn==0.34.0 \
    pydantic==2.10.6 \
    python-multipart==0.0.20 \
    requests==2.32.3 \
    Pillow==11.1.0 \
    opencv-python-headless==4.11.0.86 \
    numpy \
    easyocr==1.7.2 \
    transformers==4.48.2 \
    qwen-vl-utils==0.0.8

echo ""
echo "✅ Installation complete!"
echo ""
echo "=========================================="
echo "📋 Next Steps:"
echo "=========================================="
echo ""
echo "1. Upload your code files to: $APP_DIR"
echo ""
echo "2. Start the service:"
echo "   cd $APP_DIR"
echo "   source venv/bin/activate"
echo "   python3 main.py"
echo ""
echo "3. Or run in background with screen:"
echo "   screen -S api"
echo "   cd $APP_DIR"
echo "   source venv/bin/activate"
echo "   python3 main.py"
echo "   # Press Ctrl+A then D to detach"
echo ""
echo "4. Access your API:"
echo "   http://YOUR_VAST_PUBLIC_IP:PORT/docs"
echo ""
echo "=========================================="
