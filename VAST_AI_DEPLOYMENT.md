# Vast.ai Deployment Guide

## ✅ What You Have

- **Running Vast.ai instance**: `120.238.149.205:25752`
- **Port exposed**: 8000 (needs to be public)
- **API configured**: ✅ Already listening on `0.0.0.0:8000`

---

## 🔹 Step 1: Verify API is Listening on 0.0.0.0 ✅

Your `main.py` is already configured correctly:

```python
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
```

✅ **This is correct** - will accept connections from anywhere

---

## 🔹 Step 2: Expose Port 8000 in Vast.ai

### In Vast.ai Dashboard:

1. Go to your instance details
2. Look for **Port Mappings** section
3. Make sure port 8000 is **publicly exposed**:
   - **Internal Port**: 8000
   - **External Port**: 8000 (or mapped port)
   - **Protocol**: TCP
   - **Public**: ✅ Enabled

### If Using Docker:

```bash
docker run --gpus all -p 8000:8000 -v /opt/ai_image_checker:/app your-image
```

---

## 🔹 Step 3: Find Your Vast.ai Public IP and Port

You already have:
- **Public IP**: `120.238.149.205`
- **SSH Port**: `25752`
- **API Port**: Check Vast.ai dashboard for the mapped port for 8000

Your public URL will be:
```
http://120.238.149.205:<MAPPED_PORT>
```

Or if port 8000 is directly exposed:
```
http://120.238.149.205:8000
```

---

## 🔹 Step 4: Start Your Service on Vast.ai

### SSH into your Vast instance:

```powershell
ssh -i "C:\Users\BLG\Documents\ssh-key-ai\id_ed25519" -p 25752 root@120.238.149.205
```

### Option A: Run with Screen (Recommended)

```bash
# Install screen if needed
apt install screen -y

# Start a screen session
screen -S api-service

# Navigate and activate
cd /opt/ai_image_checker
source venv/bin/activate

# Start the service
python3 main.py

# Detach: Press Ctrl+A then D
# Reattach later: screen -r api-service
```

### Option B: Run with nohup

```bash
cd /opt/ai_image_checker
source venv/bin/activate
nohup python3 main.py > /var/log/api.log 2>&1 &
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
