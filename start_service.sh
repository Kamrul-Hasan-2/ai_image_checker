#!/bin/bash
# Start AI Image Checker Service
# Use this script to run the service without systemd

cd /opt/ai_image_checker
source venv/bin/activate

echo "=========================================="
echo "Starting AI Image Checker Service"
echo "=========================================="
echo ""
echo "Service will be available at:"
echo "  - http://localhost:8000"
echo "  - http://120.238.149.205:8000"
echo "  - API Docs: http://120.238.149.205:8000/docs"
echo ""
echo "Press Ctrl+C to stop the service"
echo ""

python3 main.py
