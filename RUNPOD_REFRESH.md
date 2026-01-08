# Force RunPod Workers to Use Latest Image

## Problem
Old workers may cache outdated Docker images. Worker `012hphkt20hkjm` is using old code with IndentationError.

## Solution Options

### Option 1: Wait for Auto-Refresh (Recommended)
- GitHub Actions is building new image now
- RunPod auto-pulls `:latest` tag within 5-10 minutes
- Worker `tuaancyslxavl8` already working with new code ✅

### Option 2: Force Refresh in RunPod Dashboard
1. Go to RunPod dashboard
2. Navigate to your endpoint
3. Click **"Force Refresh Workers"** or **"Restart Endpoint"**
4. All workers will pull latest image immediately

### Option 3: Scale Down/Up Workers
1. In RunPod dashboard, set workers to 0
2. Wait 30 seconds
3. Scale back up to desired number
4. Fresh workers will pull latest `:latest` tag

## Current Status
✅ **Code is fixed** - All Python files syntax validated
✅ **Worker `tuaancyslxavl8` working** - Hybrid system operational
❌ **Worker `012hphkt20hkjm` cached** - Using old image with error

## Docker Tags Being Built
- `kamrulhasan00/ai-image-checker:latest` (auto-pulled by RunPod)
- `kamrulhasan00/ai-image-checker:v2.0-fixed`
- `kamrulhasan00/ai-image-checker:<git-sha>` (unique per commit)

## Verify Fix
Test your endpoint. You should see in logs:
```
Starting handler import... [v2.0 OPTIMIZED]
✓ QualityCheckService imported
✓ OCRService imported
✓ CLIPService imported  <-- Should NOT have error here
✓ Qwen2VLService imported
```

If you still see the error, force refresh workers using Option 2 or 3 above.
