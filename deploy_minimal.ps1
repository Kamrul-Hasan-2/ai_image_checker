# Minimal Deployment Script for Low-Disk-Space Servers
# This installs only essential dependencies

$SSH_KEY = "C:\Users\BLG\Documents\ssh-key-ai\id_ed25519"
$SSH_PORT = "25752"
$SERVER = "root@120.238.149.205"
$LOCAL_PATH = "C:\Users\BLG\Desktop\ai_image_checker"
$REMOTE_PATH = "/opt/ai_image_checker"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Minimal Deployment - Space-Saving Mode" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Clean up space on remote server
Write-Host "[1/6] Cleaning up disk space..." -ForegroundColor Yellow
ssh -i $SSH_KEY -p $SSH_PORT $SERVER @"
apt clean
apt autoremove -y
rm -rf ~/.cache/pip
rm -rf /tmp/*
journalctl --vacuum-time=3d
echo 'Disk space after cleanup:'
df -h | grep -E 'Filesystem|/$'
"@

# Step 2: Create directory
Write-Host "[2/6] Creating remote directory..." -ForegroundColor Yellow
ssh -i $SSH_KEY -p $SSH_PORT $SERVER "mkdir -p $REMOTE_PATH"

# Step 3: Transfer essential files only
Write-Host "[3/6] Transferring essential files..." -ForegroundColor Yellow
$files = @(
    "main.py",
    "handler.py",
    "clip_service.py",
    "ocr_service.py",
    "quality_service.py",
    "qwen_service.py",
    "requirements_cpu.txt"
)

foreach ($file in $files) {
    if (Test-Path "$LOCAL_PATH\$file") {
        Write-Host "  Copying $file..." -ForegroundColor Gray
        scp -i $SSH_KEY -P $SSH_PORT "$LOCAL_PATH\$file" "${SERVER}:${REMOTE_PATH}/"
    }
}

# Step 4: Install Python essentials
Write-Host "[4/6] Installing Python environment..." -ForegroundColor Yellow
ssh -i $SSH_KEY -p $SSH_PORT $SERVER @"
cd $REMOTE_PATH
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip --no-cache-dir
"@

# Step 5: Install minimal dependencies
Write-Host "[5/6] Installing minimal dependencies (CPU-only)..." -ForegroundColor Yellow
ssh -i $SSH_KEY -p $SSH_PORT $SERVER @"
cd $REMOTE_PATH
source venv/bin/activate
pip install --no-cache-dir -r requirements_cpu.txt
"@

# Step 6: Create systemd service
Write-Host "[6/6] Setting up service..." -ForegroundColor Yellow
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
Write-Host "Minimal Deployment Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Final Steps:" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. SSH into server:" -ForegroundColor White
Write-Host "   ssh -i `"$SSH_KEY`" -p $SSH_PORT $SERVER" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Configure firewall (optional):" -ForegroundColor White
Write-Host "   apt install ufw -y" -ForegroundColor Gray
Write-Host "   ufw allow 8000/tcp" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Start the service:" -ForegroundColor White
Write-Host "   systemctl start ai-image-checker" -ForegroundColor Gray
Write-Host ""
Write-Host "4. Check status:" -ForegroundColor White
Write-Host "   systemctl status ai-image-checker" -ForegroundColor Gray
Write-Host ""
Write-Host "5. Test the API:" -ForegroundColor White
Write-Host "   curl http://localhost:8000/health" -ForegroundColor Gray
Write-Host ""
Write-Host "Access URL: http://120.238.149.205:8000/docs" -ForegroundColor Green
Write-Host ""
Write-Host "If you still have issues, see TROUBLESHOOTING.md" -ForegroundColor Yellow
Write-Host ""
