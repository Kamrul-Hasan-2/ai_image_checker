# 🚀 Vast.ai Quick Start - DO NOT USE DOCKER!

## ⚠️ Key Point
**Vast.ai is already a Docker container. Don't try to run Docker inside it!**

---

## 📋 Setup Commands (Copy & Paste)

### On your Vast.ai server, run these commands:

```bash
# 1. Navigate to workspace
cd /workspace

# 2. Upload your files (or clone from git)
# Upload all files from your local ai_image_checker folder

# 3. Navigate to your app folder
cd ai_image_checker

# 4. Run the setup script
bash setup_vast_ai.sh

# 5. Start the service
bash start_vast_ai.sh
```

---

## 🔄 Alternative: Manual Upload

If you need to transfer files from your Windows machine:

```powershell
# On your Windows PowerShell (from ai_image_checker folder)
scp -r -P YOUR_SSH_PORT * root@YOUR_VAST_IP:/workspace/ai_image_checker/
```

---

## 🎯 After Setup

Your API will be available at:
```
http://YOUR_VAST_PUBLIC_IP:PORT/docs
```

Find your public IP and port in the Vast.ai dashboard.

---

## 📱 Background Service

To keep the service running after you disconnect:

```bash
# Start screen session
screen -S api

# Start the service
cd /workspace/ai_image_checker
source venv/bin/activate
python3 main.py

# Detach: Press Ctrl+A then D
# Reconnect later: screen -r api
# Stop: screen -X -S api quit
```

---

## 🔍 Check Status

```bash
# Check if service is running
ps aux | grep python3

# Check port
netstat -tulpn | grep 8000

# View logs (if running with screen)
screen -r api

# Test locally
curl http://localhost:8000/health
```

---

## ❌ Common Mistakes to Avoid

1. ❌ Don't run `docker build` or `docker-compose` - You're already in a container!
2. ❌ Don't try to start Docker daemon - It's not available
3. ❌ Don't use systemd commands - Vast.ai doesn't use systemd
4. ✅ Just run Python directly!

---

## 🆘 Troubleshooting

**Port already in use?**
```bash
kill -9 $(lsof -t -i:8000)
```

**Can't access from outside?**
- Check Vast.ai dashboard: Port 8000 must be publicly exposed
- Test locally first: `curl http://localhost:8000/health`

**Dependencies failed?**
```bash
pip install --upgrade pip
pip install -r requirements.txt
```
