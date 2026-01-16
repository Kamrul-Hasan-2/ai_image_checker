# Troubleshooting Guide

## Error: No space left on device

### Quick Fix - Clean Up Disk Space

```bash
# Check disk usage
df -h

# Check what's using space
du -sh /* 2>/dev/null | sort -h

# Clean package cache
rm -rf ~/.cache/pip
apt clean
apt autoclean
apt autoremove -y

# Clean old logs
journalctl --vacuum-time=7d

# Find large files
find / -type f -size +100M 2>/dev/null | head -20
```

### Solution: Use CPU-Only Requirements

The GPU version requires ~5GB of CUDA libraries. Use the CPU version instead:

```bash
cd /opt/ai_image_checker
source venv/bin/activate

# Use CPU-only requirements (much smaller)
pip install -r requirements_cpu.txt
```

## Error: ufw: command not found

Install firewall tool or use iptables:

### Option A: Install UFW
```bash
apt update
apt install ufw -y
ufw allow 8000/tcp
ufw enable
```

### Option B: Use iptables (if ufw won't install)
```bash
iptables -A INPUT -p tcp --dport 8000 -j ACCEPT
iptables-save > /etc/iptables/rules.v4
```

### Option C: No firewall (less secure)
```bash
# Just make sure the service is running and accessible
# The application already binds to 0.0.0.0:8000
```

## Error: ModuleNotFoundError: No module named 'fastapi'

Dependencies not installed properly. Fix:

```bash
cd /opt/ai_image_checker

# Remove old virtual environment
rm -rf venv

# Create new virtual environment
python3 -m venv venv
source venv/bin/activate

# Upgrade pip first
pip install --upgrade pip

# Install CPU-only requirements
pip install -r requirements_cpu.txt
```

## Complete Fresh Installation Steps

```bash
# 1. Clean up space
apt clean
apt autoremove -y
rm -rf ~/.cache/pip
rm -rf /tmp/*

# 2. Check available space (need at least 2GB free)
df -h

# 3. Go to project directory
cd /opt/ai_image_checker

# 4. Remove old venv
rm -rf venv

# 5. Create new venv
python3 -m venv venv
source venv/bin/activate

# 6. Install minimal requirements
pip install --no-cache-dir fastapi uvicorn python-multipart pillow requests

# 7. Test if it runs
python3 main.py
```

## Minimal Working Installation

If you still have space issues, install only the essentials:

```bash
pip install --no-cache-dir \
  fastapi==0.115.0 \
  uvicorn==0.32.0 \
  python-multipart==0.0.12 \
  pillow==10.4.0 \
  requests==2.32.3
```

Then modify `main.py` to skip AI models temporarily (comment out model loading).

## Check Service Status

```bash
# Check if service is running
systemctl status ai-image-checker

# Check logs
journalctl -u ai-image-checker -f

# Test locally
curl http://localhost:8000/health

# Test from outside
curl http://120.238.149.205:8000/health
```

## Port Already in Use

```bash
# Find what's using port 8000
lsof -i :8000

# Kill the process
kill -9 <PID>

# Or use a different port
# Edit main.py: uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=False)
```

## SSL Certificate Errors

```bash
# Update CA certificates
apt update
apt install ca-certificates -y
update-ca-certificates
```

## Disk Space Recommendations

- **Minimum**: 2GB free for CPU-only installation
- **Recommended**: 5GB free for comfortable operation
- **With GPU**: 10GB+ free for CUDA libraries

## Performance Optimization

### Use Smaller Models

Edit service files to use smaller models:
- CLIP: `openai/clip-vit-base-patch32` (already the smallest)
- Qwen: Use `Qwen2-VL-2B-Instruct` instead of 7B version

### Reduce Workers

In `main.py`, keep single process (already configured):
```python
uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False, workers=1)
```

## Quick Test Script

Create `test_local.sh`:
```bash
#!/bin/bash
echo "Testing AI Image Checker..."
curl -X GET http://localhost:8000/health
echo ""
echo "If you see a response above, the service is working!"
```

Run with: `bash test_local.sh`
