#!/bin/bash
# Quick server restart and test script

echo "================================================"
echo "AI Image Checker - Server Reload & Test"
echo "================================================"

# Check if server is running
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "✅ Server is running on port 8000"
    echo "📋 Process info:"
    lsof -Pi :8000 -sTCP:LISTEN
    
    read -p "Do you want to restart the server? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🔄 Killing existing process..."
        kill -9 $(lsof -t -i:8000)
        sleep 2
        
        echo "🚀 Starting server..."
        nohup python main.py --port 8000 > server.log 2>&1 &
        sleep 3
    fi
else
    echo "⚠️  Server is NOT running"
    echo "🚀 Starting server..."
    nohup python main.py --port 8000 > server.log 2>&1 &
    sleep 3
fi

echo ""
echo "================================================"
echo "Testing Local Endpoints"
echo "================================================"

# Test health endpoint
echo "Testing: http://localhost:8000/image_checker/health"
curl -s http://localhost:8000/image_checker/health | python -m json.tool
echo ""

# Test root endpoint
echo "Testing: http://localhost:8000/image_checker"
curl -s http://localhost:8000/image_checker | python -m json.tool
echo ""

echo "================================================"
echo "Server logs (last 10 lines):"
echo "================================================"
tail -10 server.log

echo ""
echo "✅ Setup complete! Your endpoints:"
echo "   LOCAL:  http://localhost:8000/image_checker/health"
echo "   PUBLIC: https://ais.bdstall.com/image_checker/health"
