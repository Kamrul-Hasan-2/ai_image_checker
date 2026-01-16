# PowerShell Script to Deploy AI Image Checker to Linux Server
# Run this from Windows to transfer files to your Linux server

$SSH_KEY = "C:\Users\BLG\Documents\ssh-key-ai\id_ed25519"
$SSH_PORT = "25752"
$SERVER = "root@120.238.149.205"
$LOCAL_PATH = "C:\Users\BLG\Desktop\ai_image_checker"
$REMOTE_PATH = "/opt/ai_image_checker"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "AI Image Checker - Deployment Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Create remote directory
Write-Host "[1/4] Creating remote directory..." -ForegroundColor Yellow
ssh -i $SSH_KEY -p $SSH_PORT $SERVER "mkdir -p $REMOTE_PATH"

# Step 2: Transfer files
Write-Host "[2/4] Transferring project files..." -ForegroundColor Yellow
Write-Host "This may take a few minutes..." -ForegroundColor Gray

# Transfer essential files
$files = @(
    "main.py",
    "handler.py",
    "clip_service.py",
    "ocr_service.py",
    "quality_service.py",
    "qwen_service.py",
    "requirements.txt",
    "README.md"
)

foreach ($file in $files) {
    Write-Host "  Copying $file..." -ForegroundColor Gray
    scp -i $SSH_KEY -P $SSH_PORT "$LOCAL_PATH\$file" "${SERVER}:${REMOTE_PATH}/"
}

# Step 3: Install dependencies
Write-Host "[3/4] Installing dependencies on server..." -ForegroundColor Yellow
ssh -i $SSH_KEY -p $SSH_PORT $SERVER @"
cd $REMOTE_PATH && \
python3 -m venv venv && \
source venv/bin/activate && \
pip install --upgrade pip && \
pip install -r requirements.txt
"@

# Step 4: Create systemd service
Write-Host "[4/4] Creating systemd service..." -ForegroundColor Yellow
ssh -i $SSH_KEY -p $SSH_PORT $SERVER @"
cat > /etc/systemd/system/ai-image-checker.service << 'EOF'
[Unit]
Description=AI Image Checker FastAPI Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$REMOTE_PATH
Environment="PATH=$REMOTE_PATH/venv/bin"
ExecStart=$REMOTE_PATH/venv/bin/python3 $REMOTE_PATH/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ai-image-checker
"@

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "1. Configure firewall:" -ForegroundColor White
Write-Host "   ssh -i `"$SSH_KEY`" -p $SSH_PORT $SERVER" -ForegroundColor Gray
Write-Host "   sudo ufw allow 8000/tcp" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Start the service:" -ForegroundColor White
Write-Host "   sudo systemctl start ai-image-checker" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Check status:" -ForegroundColor White
Write-Host "   sudo systemctl status ai-image-checker" -ForegroundColor Gray
Write-Host ""
Write-Host "4. Access your API:" -ForegroundColor White
Write-Host "   http://120.238.149.205:8000/docs" -ForegroundColor Green
Write-Host ""
Write-Host "To view logs:" -ForegroundColor Cyan
Write-Host "   sudo journalctl -u ai-image-checker -f" -ForegroundColor Gray
Write-Host ""
