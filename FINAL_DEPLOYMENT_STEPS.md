# FINAL DEPLOYMENT STEPS - Manual Method

## Problem: Your server (vast.ai) has SSL certificate issues and unstable connection

## Solution: Run the service locally on Windows, then expose it

### Option 1: Run Locally on Windows (EASIEST)

1. **You already have everything installed locally**. Just run:
```powershell
cd C:\Users\BLG\Desktop\ai_image_checker
python main.py
```

2. **The service will run on http://localhost:8000**

3. **To make it accessible from outside:**
   - Configure Windows Firewall to allow port 8000
   - Use your Windows IP address instead

### Option 2: Keep Trying with vast.ai Server

The packages are downloaded at: `C:\Users\BLG\AppData\Local\Temp\ai_pkgs_py312\`

SSH into your server and run these commands ONE AT A TIME:

```bash
cd /opt/ai_image_checker
source venv/bin/activate

# Install each package individually (copy and paste one at a time)
pip install /opt/ai_image_checker/py312/typing_extensions-4.15.0-py3-none-any.whl
pip install /opt/ai_image_checker/py312/annotated_types-0.7.0-py3-none-any.whl
pip install /opt/ai_image_checker/py312/annotated_doc-0.0.4-py3-none-any.whl
pip install /opt/ai_image_checker/py312/pydantic_core-2.41.5-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl
pip install /opt/ai_image_checker/py312/typing_inspection-0.4.2-py3-none-any.whl
pip install /opt/ai_image_checker/py312/pydantic-2.12.5-py3-none-any.whl
pip install /opt/ai_image_checker/py312/idna-3.11-py3-none-any.whl
pip install /opt/ai_image_checker/py312/anyio-4.12.1-py3-none-any.whl
pip install /opt/ai_image_checker/py312/starlette-0.50.0-py3-none-any.whl
pip install /opt/ai_image_checker/py312/fastapi-0.128.0-py3-none-any.whl
pip install /opt/ai_image_checker/py312/click-8.3.1-py3-none-any.whl
pip install /opt/ai_image_checker/py312/h11-0.16.0-py3-none-any.whl
pip install /opt/ai_image_checker/py312/uvicorn-0.40.0-py3-none-any.whl
pip install /opt/ai_image_checker/py312/python_multipart-0.0.21-py3-none-any.whl
pip install /opt/ai_image_checker/py312/pillow-12.1.0-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.whl
pip install /opt/ai_image_checker/py312/certifi-2026.1.4-py3-none-any.whl
pip install /opt/ai_image_checker/py312/urllib3-2.6.3-py3-none-any.whl
pip install /opt/ai_image_checker/py312/charset_normalizer-3.4.4-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl
pip install /opt/ai_image_checker/py312/requests-2.32.5-py3-none-any.whl

# Then start the service
python3 main.py
```

### Option 3: Use Different Hosting

vast.ai seems to have network issues. Consider:

1. **DigitalOcean Droplet** ($6/month)
2. **AWS EC2 Free Tier**
3. **Google Cloud Run** (Serverless)
4. **Render.com** (Free tier available)

These providers have stable networks and proper SSL certificates.

## Testing Your Local Setup

1. Run locally:
```powershell
cd C:\Users\BLG\Desktop\ai_image_checker
python main.py
```

2. Test in another PowerShell:
```powershell
Invoke-RestMethod http://localhost:8000/health
```

3. Open in browser:
```
http://localhost:8000/docs
```

## Postman Testing (Local)

- **URL**: `http://localhost:8000/check_image`
- **Method**: POST
- **Body**: form-data
  - Key: `file` (Type: File)
  - Value: Select image file

## Next Steps

If you want public access:
1. Run locally on Windows
2. Get a domain name
3. Use ngrok or similar for tunnel: `ngrok http 8000`
4. Or deploy to a proper cloud provider (not vast.ai)

## Why vast.ai is Having Issues

- SSL certificate problems connecting to PyPI
- Unstable SSH connections
- Limited disk space
- Container environment without systemd

It's designed for GPU training, not for running web services.
