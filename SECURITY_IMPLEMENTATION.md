# API Security Implementation

## Adding API Key Authentication

To protect your public API, add API key authentication.

### 1. Create a Security Module

Create `security.py`:

```python
from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
from typing import Optional
import os

API_KEY_NAME = "X-API-Key"
API_KEY = os.getenv("API_KEY", "your-secret-api-key-change-this")

api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_api_key(api_key_header: str = Security(api_key_header)) -> str:
    if api_key_header == API_KEY:
        return api_key_header
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API Key"
    )
```

### 2. Update main.py

Add to imports:
```python
from security import get_api_key
```

Add to protected endpoints:
```python
@app.post("/check_image")
async def check_image(
    file: UploadFile = File(...),
    category: Optional[str] = Form(None),
    api_key: str = Security(get_api_key)  # Add this line
):
    # ... rest of the code
```

### 3. Set Environment Variable

On Linux server:
```bash
export API_KEY="your-super-secret-key-here"
```

Or in systemd service file:
```ini
Environment="API_KEY=your-super-secret-key-here"
```

### 4. Use in Postman

Add header to all requests:
- Key: `X-API-Key`
- Value: `your-super-secret-key-here`

## Rate Limiting

Install slowapi:
```bash
pip install slowapi
```

Add to main.py:
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/check_image")
@limiter.limit("10/minute")  # 10 requests per minute
async def check_image(...):
    # ... rest of the code
```

## IP Whitelisting

Add to main.py:
```python
from fastapi import Request

ALLOWED_IPS = ["YOUR_IP_HERE", "192.168.1.100"]

@app.middleware("http")
async def ip_whitelist(request: Request, call_next):
    client_ip = request.client.host
    if client_ip not in ALLOWED_IPS:
        raise HTTPException(status_code=403, detail="Access denied")
    return await call_next(request)
```

## HTTPS with Let's Encrypt (Recommended)

### 1. Get a Domain Name
You need a domain name pointing to 120.238.149.205

### 2. Install Certbot
```bash
sudo apt install certbot python3-certbot-nginx -y
```

### 3. Get SSL Certificate
```bash
sudo certbot --nginx -d yourdomain.com
```

### 4. Auto-renewal
```bash
sudo certbot renew --dry-run
```

Then access via: `https://yourdomain.com`

## Best Practices

1. **Always use HTTPS in production**
2. **Change default API keys**
3. **Use environment variables for secrets**
4. **Implement rate limiting**
5. **Monitor access logs**
6. **Keep dependencies updated**
7. **Use strong passwords for SSH**
8. **Consider using a firewall (ufw)**
