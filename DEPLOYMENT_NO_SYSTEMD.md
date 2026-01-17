# Manual Deployment Guide (No Systemd)

## Current Issues

1. **SSL Certificate Error** - Can't connect to PyPI
2. **No Systemd** - Server doesn't use systemd as init system
3. **Permission Issues** - Need proper sudo/root access

## Solution: Direct Installation & Running

### Step 1: Fix SSL Certificate Issues

```bash
# Update CA certificates
sudo apt update
sudo apt install --reinstall ca-certificates
sudo update-ca-certificates

# Or use pip with trusted host (temporary workaround)
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org fastapi
```

### Step 2: Manual Installation

```bash
cd /opt/ai_image_checker

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Upgrade pip with SSL workaround
python3 -m pip install --upgrade pip --trusted-host pypi.org --trusted-host files.pythonhosted.org

# Install dependencies with SSL workaround
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org --no-cache-dir \
  fastapi==0.115.0 \
  uvicorn[standard]==0.32.0 \
  python-multipart==0.0.12 \
  pillow==10.4.0 \
  requests==2.32.3 \
  numpy==1.26.4 \
  torch==2.4.1 \
  torchvision==0.19.1 \
  transformers==4.45.1 \
  --extra-index-url https://download.pytorch.org/whl/cpu
```

### Step 3: Configure Firewall (if needed)

```bash
# With sudo privileges
sudo ufw allow 8000/tcp
sudo ufw status
```

### Step 4: Run the Service Directly

**Option A: Run in Foreground (for testing)**
```bash
cd /opt/ai_image_checker
source venv/bin/activate
python3 main.py
```

**Option B: Run in Background with nohup**
```bash
cd /opt/ai_image_checker
source venv/bin/activate
nohup python3 main.py > /var/log/ai-image-checker.log 2>&1 &
echo $! > /tmp/ai-image-checker.pid
```

**Option C: Use screen (recommended for WSL/no systemd)**
```bash
# Install screen if not available
sudo apt install screen -y

# Start a new screen session
screen -S ai-image-checker

# Inside screen, run the app
cd /opt/ai_image_checker
source venv/bin/activate
python3 main.py

# Detach from screen: Press Ctrl+A then D
# Reattach later: screen -r ai-image-checker
```

### Step 5: Verify Service is Running

```bash
# Check if port 8000 is listening
netstat -tulpn | grep 8000

# Or use ss
ss -tulpn | grep 8000

# Test locally
curl http://localhost:8000/health

# Test from Windows
# Open browser: http://120.238.149.205:8000/docs
```

## Alternative: Run from Windows Script

Since systemd isn't available, use screen or tmux to keep it running.

### Create start_service.sh on Linux server:

```bash
#!/bin/bash
cd /opt/ai_image_checker
source venv/bin/activate
python3 main.py
```

Make it executable:
```bash
chmod +x /opt/ai_image_checker/start_service.sh
```

Run it:
```bash
/opt/ai_image_checker/start_service.sh
```

## WSL-Specific Instructions

If you're using WSL2, you can access it from Windows using:

1. **Find WSL IP:**
```bash
ip addr show eth0 | grep "inet\b" | awk '{print $2}' | cut -d/ -f1
```

2. **Port Forward from Windows (PowerShell as Admin):**
```powershell
netsh interface portproxy add v4tov4 listenport=8000 listenaddress=0.0.0.0 connectport=8000 connectaddress=<WSL_IP>
```

## Stopping the Service

**If using nohup:**
```bash
kill $(cat /tmp/ai-image-checker.pid)
```

**If using screen:**
```bash
screen -r ai-image-checker
# Press Ctrl+C to stop
# Exit screen: type 'exit'
```

**Find and kill process:**
```bash
ps aux | grep main.py
kill <PID>
```

## Auto-start on Boot (Without Systemd)

Add to `/etc/rc.local` (if available):
```bash
#!/bin/bash
cd /opt/ai_image_checker && source venv/bin/activate && nohup python3 main.py > /var/log/ai-image-checker.log 2>&1 &
exit 0
```

Make it executable:
```bash
sudo chmod +x /etc/rc.local
```

## Quick Test

```bash
# After starting the service
curl -X GET http://localhost:8000/health

# Should return: {"status":"ok"}
```

## Accessing from Postman

Once running:
- **URL**: `http://120.238.149.205:8000`
- **Docs**: `http://120.238.149.205:8000/docs`

Test endpoint:
- Method: GET
- URL: `http://120.238.149.205:8000/health`
