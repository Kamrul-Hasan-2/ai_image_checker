# Public Deployment Guide

## Making Your Service Publicly Accessible

Your FastAPI service is already configured to bind to `0.0.0.0:8000`, which allows it to accept connections from any IP address.

## Steps to Deploy on Your Linux Server (120.238.149.205)

### 1. Connect to Your Server
```bash
ssh -i "C:\Users\BLG\Documents\ssh-key-ai\id_ed25519" -p 25752 root@120.238.149.205
```

### 2. Install Dependencies on Linux Server

```bash
# Update system
sudo apt update

# Install Python and pip
sudo apt install python3 python3-pip python3-venv -y

# Create project directory
mkdir -p /opt/ai_image_checker
cd /opt/ai_image_checker
```

### 3. Transfer Project Files

**Option A: Using SCP from Windows**
```powershell
scp -i "C:\Users\BLG\Documents\ssh-key-ai\id_ed25519" -P 25752 -r C:\Users\BLG\Desktop\ai_image_checker\* root@120.238.149.205:/opt/ai_image_checker/
```

**Option B: Using Git (if your project is in a repository)**
```bash
git clone <your-repo-url> /opt/ai_image_checker
cd /opt/ai_image_checker
```

### 4. Set Up Python Environment

```bash
cd /opt/ai_image_checker

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 5. Configure Firewall

```bash
# Allow port 8000 through firewall
sudo ufw allow 8000/tcp

# Check firewall status
sudo ufw status
```

### 6. Run the Application

**Option A: Direct Run (for testing)**
```bash
python3 main.py
```

**Option B: Using systemd (recommended for production)**
Create a systemd service file:

```bash
sudo nano /etc/systemd/system/ai-image-checker.service
```

Add this content:
```ini
[Unit]
Description=AI Image Checker FastAPI Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/ai_image_checker
Environment="PATH=/opt/ai_image_checker/venv/bin"
ExecStart=/opt/ai_image_checker/venv/bin/python3 /opt/ai_image_checker/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable ai-image-checker
sudo systemctl start ai-image-checker
sudo systemctl status ai-image-checker
```

### 7. Access Your Service

Once running, your service will be accessible at:
- **Public URL**: `http://120.238.149.205:8000`
- **API Documentation**: `http://120.238.149.205:8000/docs`

## Testing with Postman

1. Open Postman
2. Create a new POST request to: `http://120.238.149.205:8000/check_image`
3. Set Headers:
   - Content-Type: `multipart/form-data`
4. In Body, select "form-data":
   - Key: `file` (set type to File)
   - Value: Select your image file
5. Send the request

## Security Considerations

⚠️ **IMPORTANT**: Currently, your service is open to the public without authentication. Consider these security measures:

### 1. Add API Key Authentication
I can help you implement this - see `SECURITY_IMPLEMENTATION.md`

### 2. Use NGINX as Reverse Proxy
```bash
sudo apt install nginx -y
```

Create NGINX config at `/etc/nginx/sites-available/ai-image-checker`:
```nginx
server {
    listen 80;
    server_name 120.238.149.205;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

Enable and restart NGINX:
```bash
sudo ln -s /etc/nginx/sites-available/ai-image-checker /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

Then access via: `http://120.238.149.205` (port 80)

### 3. Use HTTPS with Let's Encrypt
```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d yourdomain.com
```

## Monitoring

View service logs:
```bash
# If using systemd
sudo journalctl -u ai-image-checker -f

# If running directly
# Check the terminal output
```

## Troubleshooting

### Service not accessible
1. Check if service is running: `sudo systemctl status ai-image-checker`
2. Check firewall: `sudo ufw status`
3. Check if port is listening: `sudo netstat -tlnp | grep 8000`
4. Test locally on server: `curl http://localhost:8000/health`

### Models not loading
- Ensure sufficient RAM (requires ~8GB for models)
- Check disk space: `df -h`
- Check logs for errors

## Postman Collection Example

Here's a complete example for your Postman collection:

### Endpoint 1: Health Check
```
GET http://120.238.149.205:8000/health
```

### Endpoint 2: Check Image (File Upload)
```
POST http://120.238.149.205:8000/check_image
Body: form-data
  - file: [image file]
  - category: "electronics" (optional)
```

### Endpoint 3: Check Image (URL)
```
POST http://120.238.149.205:8000/check_image_url
Body: raw JSON
{
  "image_url": "https://example.com/image.jpg",
  "category": "electronics"
}
```

### Endpoint 4: Dispute Resolution
```
POST http://120.238.149.205:8000/dispute
Body: form-data
  - file: [image file]
  - decision: "REJECT"
  - reason: "Contains inappropriate content"
  - context: "User disagrees with moderation decision"
```
