# Vast.ai Deployment Guide

## ⚠️ Important: Don't Use Docker on Vast.ai!

Vast.ai instances already run inside containers. You should run your application **directly** without Docker.

---

## 🚀 Quick Setup (3 Steps)

### Step 1: SSH into your Vast.ai instance

```bash
ssh -p YOUR_PORT root@YOUR_VAST_IP
```

### Step 2: Download and run setup script

```bash
# Navigate to workspace
cd /workspace

# Clone or upload your code
# (You can use scp, git, or Vast.ai's file upload)

# Run setup
cd ai_image_checker
bash setup_vast_ai.sh
```

### Step 3: Start the service

```bash
bash start_vast_ai.sh
```

Or run in background with screen:
```bash
screen -S api
bash start_vast_ai.sh
# Press Ctrl+A then D to detach
# Reconnect with: screen -r api
```

---

## 📋 Manual Setup Instructions

If you prefer manual setup or the script doesn't work:

### 1. Install System Dependencies

```bash
apt-get update
apt-get install -y python3-pip python3-venv libgl1-mesa-glx libglib2.0-0 screen
```

### 2. Setup Python Environment

```bash
cd /workspace/ai_image_checker
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
```

### 3. Install PyTorch (GPU)

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### 4. Install Application Dependencies

```bash
pip install fastapi uvicorn pydantic python-multipart requests Pillow opencv-python-headless numpy easyocr transformers qwen-vl-utils
```

### 5. Start the Service

```bash
python3 main.py
```

---

## 🌐 Port Configuration

### In Vast.ai Dashboard:

1. Go to your instance details
2. Click **"Edit"** on your instance
3. Under **Port Mappings**, ensure port 8000 is exposed:
   - **Container Port**: 8000
   - **Make it public**: ✅ Checked

### Find Your Public URL:

Your API will be available at:
```
http://YOUR_VAST_PUBLIC_IP:MAPPED_PORT
```

Check the Vast.ai dashboard for the exact port mapping.

---

## 🔍 Troubleshooting

### Service won't start?

```bash
# Check if port 8000 is already in use
lsof -i :8000
netstat -tulpn | grep 8000

# Kill existing process if needed
kill -9 $(lsof -t -i:8000)
```

### Can't connect from outside?

1. Verify port 8000 is exposed in Vast.ai dashboard
2. Check firewall rules: `iptables -L`
3. Verify service is listening: `netstat -tulpn | grep 8000`
4. Test locally first: `curl http://localhost:8000/health`

### Out of memory?

```bash
# Check memory usage
free -h

# Choose a Vast.ai instance with more RAM (16GB+ recommended)
```

### GPU not detected?

```bash
# Check GPU availability
nvidia-smi

# Verify PyTorch can see GPU
python3 -c "import torch; print(torch.cuda.is_available())"
```

---

## 🔹 Step 5: Test from Postman

### Endpoint 1: Health Check

**Method**: GET  
**URL**: 
```
http://120.238.149.205:8000/health
```

**Expected Response**:
```json
{
  "status": "healthy",
  "services": {
    "quality": true,
    "ocr": true,
    "clip": true,
    "qwen2b": false,
    "qwen7b": false
  }
}
```

---

### Endpoint 2: Check Image (File Upload)

**Method**: POST  
**URL**: 
```
http://120.238.149.205:8000/check_image
```

**Headers**: (Auto-set by Postman for multipart)
```
Content-Type: multipart/form-data
```

**Body**: Select `form-data`
- **Key**: `file` (Type: File)
- **Value**: Choose an image file
- **Key**: `category` (Type: Text) [Optional]
- **Value**: `electronics`

**Expected Response**:
```json
{
  "success": true,
  "filename": "test.jpg",
  "pipeline_steps": [
    {
      "step": "quality_check",
      "passed": true,
      "score": 0.95
    },
    {
      "step": "ocr_check",
      "text_detected": false
    },
    {
      "step": "clip_check",
      "category": "electronics",
      "confidence": 0.87,
      "decision": "APPROVE"
    }
  ],
  "final_decision": "APPROVE",
  "processing_time_ms": 234
}
```

---

### Endpoint 3: Check Image (URL)

**Method**: POST  
**URL**: 
```
http://120.238.149.205:8000/check_image_url
```

**Headers**:
```
Content-Type: application/json
```

**Body**: Select `raw` → `JSON`
```json
{
  "image_url": "https://example.com/image.jpg",
  "category": "electronics"
}
```

---

### Endpoint 4: Dispute Resolution

**Method**: POST  
**URL**: 
```
http://120.238.149.205:8000/dispute
```

**Body**: `form-data`
- **Key**: `file` (Type: File)
- **Key**: `decision` (Type: Text) → `REJECT`
- **Key**: `reason` (Type: Text) → `Contains inappropriate content`
- **Key**: `context` (Type: Text) → `User disagrees with moderation`

---

## 🔍 Troubleshooting

### Issue 1: "Connection refused"

```bash
# Check if service is running
ps aux | grep main.py

# Check if port is listening
netstat -tlnp | grep 8000

# Or use ss
ss -tlnp | grep 8000
```

**Should show**:
```
tcp  0  0  0.0.0.0:8000  0.0.0.0:*  LISTEN  <PID>/python3
```

---

### Issue 2: "Connection timeout"

**Check Vast.ai port mapping**:
1. Go to Vast.ai dashboard
2. Check if port 8000 is exposed publicly
3. Get the correct external port number

**Check firewall** (if iptables is available):
```bash
iptables -L -n | grep 8000
```

---

### Issue 3: Service not starting

**View logs**:
```bash
# If using screen
screen -r api-service

# If using nohup
tail -f /var/log/api.log

# Check dependencies
cd /opt/ai_image_checker
source venv/bin/activate
pip list | grep fastapi
```

---

## 📋 Complete Deployment Checklist

- [ ] Files transferred to `/opt/ai_image_checker`
- [ ] Python packages installed in venv
- [ ] Port 8000 exposed in Vast.ai dashboard
- [ ] Service started with screen or nohup
- [ ] Health check responds: `curl http://localhost:8000/health`
- [ ] Public URL accessible from Postman
- [ ] Test image upload works
- [ ] API returns expected responses

---

## 🚀 Quick Start Commands

Run these in order on your Vast.ai instance:

```bash
# 1. Navigate to project
cd /opt/ai_image_checker

# 2. Activate environment
source venv/bin/activate

# 3. Install dependencies (if not done)
pip install fastapi uvicorn python-multipart pillow requests

# 4. Test locally first
python3 main.py &
sleep 5
curl http://localhost:8000/health

# 5. If working, restart in screen
pkill -f main.py
screen -S api-service
python3 main.py
# Press Ctrl+A then D to detach
```

---

## 📱 Postman Collection Import

Save this as `vast-ai-api.postman_collection.json`:

```json
{
  "info": {
    "name": "Vast.ai AI Image Checker",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "item": [
    {
      "name": "Health Check",
      "request": {
        "method": "GET",
        "header": [],
        "url": {
          "raw": "http://120.238.149.205:8000/health",
          "protocol": "http",
          "host": ["120", "238", "149", "205"],
          "port": "8000",
          "path": ["health"]
        }
      }
    },
    {
      "name": "Check Image (Upload)",
      "request": {
        "method": "POST",
        "header": [],
        "body": {
          "mode": "formdata",
          "formdata": [
            {
              "key": "file",
              "type": "file",
              "src": []
            },
            {
              "key": "category",
              "value": "electronics",
              "type": "text"
            }
          ]
        },
        "url": {
          "raw": "http://120.238.149.205:8000/check_image",
          "protocol": "http",
          "host": ["120", "238", "149", "205"],
          "port": "8000",
          "path": ["check_image"]
        }
      }
    },
    {
      "name": "Check Image (URL)",
      "request": {
        "method": "POST",
        "header": [
          {
            "key": "Content-Type",
            "value": "application/json"
          }
        ],
        "body": {
          "mode": "raw",
          "raw": "{\n  \"image_url\": \"https://example.com/test.jpg\",\n  \"category\": \"electronics\"\n}"
        },
        "url": {
          "raw": "http://120.238.149.205:8000/check_image_url",
          "protocol": "http",
          "host": ["120", "238", "149", "205"],
          "port": "8000",
          "path": ["check_image_url"]
        }
      }
    }
  ]
}
```

Import this into Postman: **Import** → **Upload Files** → Select this JSON file

---

## 🔐 Security Note

⚠️ **Your API is currently PUBLIC without authentication**

Anyone with the URL can use it. To secure:

1. **Add API Key** (see `SECURITY_IMPLEMENTATION.md`)
2. **Use NGINX reverse proxy** with basic auth
3. **Implement rate limiting**
4. **Monitor access logs**

---

## 💡 Pro Tips

1. **Keep screen session running**: Your API stays active even if SSH disconnects
2. **Monitor logs**: `screen -r api-service` to see real-time logs
3. **Check Vast.ai billing**: Make sure your instance doesn't run out of credits
4. **Backup your work**: Vast.ai instances can be terminated anytime

---

## 📞 Support

If you get stuck:

1. Check logs: `screen -r api-service`
2. Test locally first: `curl http://localhost:8000/health`
3. Verify port mapping in Vast.ai dashboard
4. Check if service is listening: `netstat -tlnp | grep 8000`
