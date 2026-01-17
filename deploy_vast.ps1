# PowerShell Script: Deploy to Vast.ai and Start Service

$SSH_KEY = "C:\Users\BLG\Documents\ssh-key-ai\id_ed25519"
$SSH_PORT = "25752"
$SERVER = "root@120.238.149.205"
$LOCAL_PATH = "C:\Users\BLG\Desktop\ai_image_checker"
$REMOTE_PATH = "/opt/ai_image_checker"

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "   Vast.ai Deployment & Startup" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Transfer essential files
Write-Host "[1/3] Transferring files to Vast.ai..." -ForegroundColor Yellow

$essentialFiles = @(
    "main.py",
    "handler.py",
    "clip_service.py",
    "ocr_service.py",
    "quality_service.py",
    "qwen_service.py",
    "vast_quickstart.sh"
)

foreach ($file in $essentialFiles) {
    if (Test-Path "$LOCAL_PATH\$file") {
        Write-Host "  → $file" -ForegroundColor Gray
        scp -i $SSH_KEY -P $SSH_PORT "$LOCAL_PATH\$file" "${SERVER}:${REMOTE_PATH}/" 2>$null
    }
}

# Step 2: Make script executable
Write-Host ""
Write-Host "[2/3] Setting up quickstart script..." -ForegroundColor Yellow
ssh -i $SSH_KEY -p $SSH_PORT $SERVER "chmod +x $REMOTE_PATH/vast_quickstart.sh"

# Step 3: Show instructions
Write-Host ""
Write-Host "[3/3] Ready to start!" -ForegroundColor Yellow
Write-Host ""
Write-Host "=========================================" -ForegroundColor Green
Write-Host "   Files Transferred Successfully!" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
Write-Host ""
Write-Host "🚀 To START your service:" -ForegroundColor Cyan
Write-Host ""
Write-Host "1️⃣  SSH into your Vast.ai instance:" -ForegroundColor White
Write-Host "   ssh -i `"$SSH_KEY`" -p $SSH_PORT $SERVER" -ForegroundColor Gray
Write-Host ""
Write-Host "2️⃣  Run the quickstart script:" -ForegroundColor White
Write-Host "   /opt/ai_image_checker/vast_quickstart.sh" -ForegroundColor Gray
Write-Host ""
Write-Host "   OR use screen to run in background:" -ForegroundColor White
Write-Host "   screen -S api" -ForegroundColor Gray
Write-Host "   /opt/ai_image_checker/vast_quickstart.sh" -ForegroundColor Gray
Write-Host "   # Press Ctrl+A then D to detach" -ForegroundColor DarkGray
Write-Host ""
Write-Host "📍 Your API will be available at:" -ForegroundColor Cyan
Write-Host "   http://120.238.149.205:8000/docs" -ForegroundColor Green
Write-Host ""
Write-Host "📚 See VAST_AI_DEPLOYMENT.md for full guide" -ForegroundColor Yellow
Write-Host ""

# Option to SSH directly
Write-Host "Would you like to SSH in now? (Y/N): " -ForegroundColor Yellow -NoNewline
$response = Read-Host

if ($response -eq 'Y' -or $response -eq 'y') {
    Write-Host ""
    Write-Host "Connecting to Vast.ai..." -ForegroundColor Green
    Write-Host ""
    ssh -i $SSH_KEY -p $SSH_PORT $SERVER
}
else {
    Write-Host ""
    Write-Host "✅ Done! SSH in when ready." -ForegroundColor Green
}
