# 🚀 Quick Server Management (Linux)

## Make scripts executable (one-time setup)
```bash
cd ~/ai_image_checker
chmod +x restart.sh start.sh stop.sh
```

## Restart Server
```bash
./restart.sh
```

## Start Server
```bash
./start.sh
```

## Stop Server
```bash
./stop.sh
```

## View Logs
```bash
# Follow logs in real-time
tail -f server.log

# View last 50 lines
tail -50 server.log

# View errors only
grep -i error server.log
```

## Check Server Status
```bash
# Check if server is running
lsof -i:8000

# Test health endpoint
curl http://localhost:8000/image_checker/health

# Test public endpoint
curl https://ais.bdstall.com/image_checker/health
```

## Troubleshooting

### Port already in use
```bash
# Find process using port 8000
lsof -ti:8000

# Kill it
kill -9 $(lsof -ti:8000)
```

### Check what went wrong
```bash
# View recent logs
tail -100 server.log

# Check Python errors
grep "Traceback" server.log -A 20
```

### Test if dependencies are installed
```bash
python3 -c "import fastapi, PIL, torch, transformers, easyocr; print('✅ All dependencies OK')"
```

## Nginx Configuration

After updating code, reload nginx:
```bash
sudo nginx -t          # Test config
sudo nginx -s reload   # Reload nginx
```

## Complete Restart Workflow
```bash
cd ~/ai_image_checker
./restart.sh           # Restart FastAPI server
sudo nginx -s reload   # Reload nginx
curl https://ais.bdstall.com/image_checker/health  # Test
```
