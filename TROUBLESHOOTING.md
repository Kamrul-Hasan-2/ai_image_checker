# 🔧 Troubleshooting "Not Found" Error

## Issue
`https://ais.bdstall.com/image_checker/health` returns "Not Found"

## Solution - Step by Step

### 1️⃣ Test Local Server First

```powershell
# Test if server is running locally
python test_local.py
```

Expected output:
```json
{
  "status": "healthy",
  "service": "AI Image Checker",
  "version": "1.0.0",
  "ready": true
}
```

### 2️⃣ If Local Test FAILS - Restart Server

**On Windows:**
```powershell
.\restart_server.bat
```

**On Linux:**
```bash
chmod +x reload_and_test.sh
./reload_and_test.sh
```

Or manually:
```bash
# Kill existing process
pkill -f "python main.py"

# Start server
nohup python main.py --port 8000 > server.log 2>&1 &

# Check logs
tail -f server.log
```

### 3️⃣ If Local Test WORKS but Public URL Fails - Check Nginx

The issue is likely with nginx configuration.

**Check nginx config:**
```bash
sudo nginx -t
```

**Your nginx config should have:**
```nginx
location /image_checker {
    proxy_pass http://127.0.0.1:8000;
    # ... other settings
}
```

**⚠️ IMPORTANT:** No trailing slash or path in `proxy_pass`!

❌ **WRONG:** `proxy_pass http://127.0.0.1:8000/;`  
✅ **CORRECT:** `proxy_pass http://127.0.0.1:8000;`

**Apply nginx config:**
```bash
# Copy config
sudo cp nginx_example.conf /etc/nginx/sites-available/ais.bdstall.com

# Enable site
sudo ln -sf /etc/nginx/sites-available/ais.bdstall.com /etc/nginx/sites-enabled/

# Test config
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

### 4️⃣ Check Server Logs

```bash
# FastAPI logs
tail -f server.log

# Nginx access logs
sudo tail -f /var/log/nginx/access.log

# Nginx error logs
sudo tail -f /var/log/nginx/error.log
```

### 5️⃣ Test Public Endpoint

```bash
# From server
curl http://localhost:8000/image_checker/health

# From anywhere
curl https://ais.bdstall.com/image_checker/health
```

## Common Issues

### Issue: nginx "502 Bad Gateway"
**Solution:** FastAPI server is not running
```bash
ps aux | grep "main.py"
python main.py --port 8000
```

### Issue: nginx "404 Not Found"  
**Solution:** Wrong nginx proxy_pass configuration
- Check if `proxy_pass` has trailing slash
- Should be: `proxy_pass http://127.0.0.1:8000;`

### Issue: Port 8000 already in use
**Solution:** Kill existing process
```bash
# Linux
lsof -ti:8000 | xargs kill -9

# Windows
netstat -ano | findstr :8000
taskkill /PID <pid> /F
```

## Quick Check Commands

```bash
# Is server running?
curl http://localhost:8000/image_checker/health

# Is nginx forwarding correctly?
curl -v https://ais.bdstall.com/image_checker/health

# Check what's listening on port 8000
netstat -tulpn | grep 8000  # Linux
netstat -ano | findstr :8000  # Windows
```

## Final Verification

All these should return `{"status": "healthy", ...}`:

1. ✅ `http://localhost:8000/image_checker/health`
2. ✅ `http://localhost:8000/image_checker`
3. ✅ `https://ais.bdstall.com/image_checker/health`
4. ✅ `https://ais.bdstall.com/image_checker`

---

**Still not working?** Check:
- [ ] FastAPI server is running: `ps aux | grep main.py`
- [ ] Server is on port 8000: `netstat -tulpn | grep 8000`
- [ ] Nginx is running: `sudo systemctl status nginx`
- [ ] Firewall allows port 8000: `sudo ufw status`
- [ ] SSL certificate is valid: `sudo certbot certificates`
