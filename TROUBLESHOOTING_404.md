# Troubleshooting 404 Errors

## Common 404 Scenarios & Solutions

### ❌ Scenario 1: Service Not Running
**Error**: Connection refused or 404 on all endpoints

**Check**:
```bash
# SSH into server
ssh -i "C:\Users\BLG\Documents\ssh-key-ai\id_ed25519" -p 25752 root@120.238.149.205

# Check if Python process is running
ps aux | grep main.py

# Check if port is listening
netstat -tlnp | grep 8000
```

**Solution**: Start the service
```bash
cd /opt/ai_image_checker
source venv/bin/activate
python3 main.py
```

---

### ❌ Scenario 2: Wrong URL
**Error**: 404 Not Found

Common mistakes:
- ❌ `http://120.238.149.205:25752` (SSH port, not API port)
- ❌ `http://120.238.149.205:8000/api/check_image` (no `/api` prefix)
- ❌ `https://120.238.149.205:8000` (should be `http`, not `https`)

✅ **Correct URLs**:
```
http://120.238.149.205:8000/
http://120.238.149.205:8000/health
http://120.238.149.205:8000/check_image
http://120.238.149.205:8000/docs
```

---

### ❌ Scenario 3: Port Not Exposed
**Error**: Connection timeout

**Check Vast.ai Dashboard**:
1. Go to your instance
2. Look for "Port Mappings" or "Network"
3. Verify port 8000 is:
   - ✅ Exposed publicly
   - ✅ Mapped to 8000 (or note the external port)

**Example**: If Vast.ai maps internal 8000 → external 18000:
```
http://120.238.149.205:18000/
```

---

### ✅ Working Service - Expected Responses

#### GET http://120.238.149.205:8000/
```json
{
  "service": "AI Image Checker API",
  "status": "running",
  "version": "3.0.0",
  "pipeline": "Quality → OCR → CLIP → Qwen2B (7B disabled)",
  "endpoints": {
    "docs": "/docs",
    "health": "/health",
    "check_image": "POST /check_image (upload file)",
    "check_image_url": "POST /check_image_url (provide URL)",
    "dispute": "POST /dispute",
    "quality": "POST /quality",
    "ocr": "POST /ocr",
    "clip_category": "POST /clip/category",
    "clip_risk": "POST /clip/risk"
  },
  "message": "Visit /docs for interactive API documentation"
}
```

#### GET http://120.238.149.205:8000/health
```json
{
  "status": "healthy",
  "version": "3.0.0",
  "pipeline": "Quality → OCR → CLIP → Qwen2B (7B disabled)",
  "models": {
    "Step 1: Quality": "✓ Loaded",
    "Step 2: OCR": "✓ Loaded",
    "Step 3: CLIP": "✓ Loaded",
    "Step 4: Qwen2B": "✓ Loaded"
  }
}
```

---

## Quick Diagnostic Steps

### Step 1: Test Locally on Server
```bash
# SSH into server
ssh -i "C:\Users\BLG\Documents\ssh-key-ai\id_ed25519" -p 25752 root@120.238.149.205

# Test from inside server
curl http://localhost:8000/health
```

**If this works** ✅ → Service is running, check port mapping  
**If this fails** ❌ → Service not running or dependencies missing

---

### Step 2: Test Public Access from Windows
```powershell
# From your Windows PC
Invoke-RestMethod http://120.238.149.205:8000/health
```

**If this works** ✅ → Port is exposed correctly  
**If this fails** ❌ → Check Vast.ai port mapping

---

### Step 3: Test in Browser
Open: `http://120.238.149.205:8000/docs`

**If this works** ✅ → You can use the interactive API  
**If 404** ❌ → Service not running or wrong port

---

## Quick Fix: Run Service Now

```bash
# SSH into server
ssh -i "C:\Users\BLG\Documents\ssh-key-ai\id_ed25519" -p 25752 root@120.238.149.205

# Navigate to project
cd /opt/ai_image_checker

# Activate environment
source venv/bin/activate

# Start service (stays in foreground)
python3 main.py
```

**Keep this terminal open** - Service runs as long as terminal is open

For background running, use `screen`:
```bash
screen -S api
python3 main.py
# Press Ctrl+A then D to detach
```

---

## Postman 404 Fix

### Issue: 404 on POST requests

**Check these**:
1. ✅ URL is correct: `http://120.238.149.205:8000/check_image`
2. ✅ Method is POST (not GET)
3. ✅ Body type is `form-data` (not JSON for file uploads)
4. ✅ Key name is `file` (exactly, lowercase)

### Example Working Request

**URL**: `http://120.238.149.205:8000/check_image`  
**Method**: POST  
**Body**: form-data
- Key: `file` | Type: File | Value: [select image]
- Key: `category` | Type: Text | Value: `electronics`

---

## Still Getting 404?

Run this diagnostic:

```bash
# Check what's listening on port 8000
netstat -tlnp | grep 8000

# Should show:
# tcp  0  0  0.0.0.0:8000  0.0.0.0:*  LISTEN  12345/python3

# Check service logs
journalctl -u ai-image-checker -f

# Or if running manually, check terminal output
```

---

## Alternative: Run Locally on Windows

If Vast.ai is problematic, run on your Windows PC:

```powershell
cd C:\Users\BLG\Desktop\ai_image_checker
python main.py
```

Then test: `http://localhost:8000/health`

---

## Contact Points

- 📍 Root: `http://120.238.149.205:8000/`
- 🏥 Health: `http://120.238.149.205:8000/health`
- 📚 Docs: `http://120.238.149.205:8000/docs`
- 🔍 API: `http://120.238.149.205:8000/check_image`

All should return JSON (not 404).
