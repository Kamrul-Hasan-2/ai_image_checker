# Deploy Script for Non-Systemd Environments (WSL/Docker/Manual)

$SSH_KEY = "C:\Users\BLG\Documents\ssh-key-ai\id_ed25519"
$SSH_PORT = "25752"
$SERVER = "root@120.238.149.205"
$LOCAL_PATH = "C:\Users\BLG\Desktop\ai_image_checker"
$REMOTE_PATH = "/opt/ai_image_checker"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "No-Systemd Deployment (WSL/Container)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Create directory
Write-Host "[1/5] Creating remote directory..." -ForegroundColor Yellow
ssh -i $SSH_KEY -p $SSH_PORT $SERVER "mkdir -p $REMOTE_PATH"

# Step 2: Transfer files
Write-Host "[2/5] Transferring files..." -ForegroundColor Yellow
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

# Step 3: Create startup script
Write-Host "[3/5] Creating startup script..." -ForegroundColor Yellow
ssh -i $SSH_KEY -p $SSH_PORT $SERVER @"
cat > $REMOTE_PATH/start_service.sh << 'SCRIPT_EOF'
#!/bin/bash
cd $REMOTE_PATH
source venv/bin/activate
python3 main.py
SCRIPT_EOF

chmod +x $REMOTE_PATH/start_service.sh
"@

# Step 4: Install dependencies with SSL workaround
Write-Host "[4/5] Installing dependencies (with SSL fix)..." -ForegroundColor Yellow
Write-Host "  This may take 5-10 minutes..." -ForegroundColor Gray
ssh -i $SSH_KEY -p $SSH_PORT $SERVER @"
cd $REMOTE_PATH

# Clean up
rm -rf ~/.cache/pip
rm -rf venv

# Update CA certificates
apt update 2>/dev/null
apt install --reinstall ca-certificates -y 2>/dev/null
update-ca-certificates 2>/dev/null

# Create venv
python3 -m venv venv
source venv/bin/activate

# Upgrade pip with SSL workaround
python3 -m pip install --upgrade pip --trusted-host pypi.org --trusted-host files.pythonhosted.org --no-cache-dir

# Install minimal dependencies
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org --no-cache-dir \
  fastapi==0.115.0 \
  uvicorn[standard]==0.32.0 \
  python-multipart==0.0.12 \
  pillow==10.4.0 \
  requests==2.32.3 \
  numpy==1.26.4

echo 'Basic dependencies installed successfully!'
"@

# Step 5: Instructions for manual start
Write-Host "[5/5] Setup complete!" -ForegroundColor Yellow

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "To START the service:" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. SSH into your server:" -ForegroundColor White
Write-Host "   ssh -i `"$SSH_KEY`" -p $SSH_PORT $SERVER" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Run using SCREEN (recommended):" -ForegroundColor White
Write-Host "   apt install screen -y" -ForegroundColor Gray
Write-Host "   screen -S ai-checker" -ForegroundColor Gray
Write-Host "   cd $REMOTE_PATH && source venv/bin/activate && python3 main.py" -ForegroundColor Gray
Write-Host "   # Press Ctrl+A then D to detach" -ForegroundColor DarkGray
Write-Host ""
Write-Host "   Or simply run:" -ForegroundColor White
Write-Host "   $REMOTE_PATH/start_service.sh" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Test the service:" -ForegroundColor White
Write-Host "   curl http://localhost:8000/health" -ForegroundColor Gray
Write-Host ""
Write-Host "4. Access from anywhere:" -ForegroundColor White
Write-Host "   http://120.238.149.205:8000/docs" -ForegroundColor Green
Write-Host ""
Write-Host "To STOP the service:" -ForegroundColor Cyan
Write-Host "   Press Ctrl+C in the terminal" -ForegroundColor Gray
Write-Host "   Or: screen -r ai-checker (then Ctrl+C)" -ForegroundColor Gray
Write-Host ""
Write-Host "See DEPLOYMENT_NO_SYSTEMD.md for more details" -ForegroundColor Yellow
Write-Host ""
