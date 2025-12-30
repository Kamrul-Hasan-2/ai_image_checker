# Docker Setup Guide for AI Image Checker

## Prerequisites

- Docker installed ([Get Docker](https://docs.docker.com/get-docker/))
- Docker Compose installed (included with Docker Desktop)
- At least 8GB RAM available
- 10GB disk space for models and dependencies

## Quick Start

### 1. Build the Docker Image

```bash
docker-compose build
```

This will:
- Install all dependencies
- Pre-download EasyOCR models
- Set up the application environment

**Note:** First build takes 10-15 minutes depending on your internet speed.

### 2. Start the Service

```bash
docker-compose up
```

Or run in detached mode:
```bash
docker-compose up -d
```

### 3. Check Service Status

```bash
docker-compose ps
```

### 4. View Logs

```bash
docker-compose logs -f
```

### 5. Test the API

Wait for the models to load (check logs for "Application startup complete"), then test:

```bash
curl -X POST http://localhost:8000/api/ai_check_detectction \
  -H "Content-Type: application/json" \
  -d '{"image_url": "https://example.com/image.jpg"}'
```

### 6. Stop the Service

```bash
docker-compose down
```

## Alternative: Using Docker Directly

### Build

```bash
docker build -t ai-image-checker .
```

### Run

```bash
docker run -d \
  --name ai-image-checker \
  -p 8000:8000 \
  -v ai-models:/app/.cache/huggingface \
  ai-image-checker
```

### Stop

```bash
docker stop ai-image-checker
docker rm ai-image-checker
```

## Configuration

### Port Configuration

Change the port in `docker-compose.yml`:
```yaml
ports:
  - "9000:8000"  # Access on port 9000 instead
```

### Resource Limits

Adjust CPU and memory in `docker-compose.yml`:
```yaml
deploy:
  resources:
    limits:
      cpus: '8'      # Use up to 8 CPU cores
      memory: 16G    # Use up to 16GB RAM
```

### GPU Support (NVIDIA)

1. Install [nvidia-docker](https://github.com/NVIDIA/nvidia-docker)

2. Uncomment GPU sections in `docker-compose.yml`:
```yaml
runtime: nvidia
environment:
  - NVIDIA_VISIBLE_DEVICES=all
```

3. Run:
```bash
docker-compose up
```

## Model Cache

Models are cached in a Docker volume (`huggingface-cache`) to avoid re-downloading on restart.

### View cached models:
```bash
docker volume inspect ai_image_checker_huggingface-cache
```

### Clear model cache:
```bash
docker-compose down -v
```

## Development Mode

To mount your code for live development:

1. Uncomment in `docker-compose.yml`:
```yaml
volumes:
  - ./:/app
```

2. Restart:
```bash
docker-compose restart
```

Changes to Python files will require manual restart since hot-reload isn't enabled by default.

## Troubleshooting

### Issue: Container exits immediately

**Check logs:**
```bash
docker-compose logs
```

**Common causes:**
- Not enough memory (need 8GB+)
- Model download failed (check internet)

### Issue: Models downloading at runtime

**Pre-download during build:**
Models should download during `docker build`. If not, the container will download on first run (takes 10-15 minutes).

### Issue: Out of memory

**Increase Docker memory:**
- Docker Desktop: Settings → Resources → Memory (set to 8GB+)

**Or reduce model memory in code:**
- Use Qwen2-VL-2B instead of 7B (already configured)

### Issue: Slow performance

**Solutions:**
- Use GPU support (see GPU section)
- Increase CPU/memory limits
- Reduce concurrent requests

## Production Deployment

### 1. Build optimized image:
```bash
docker build -t ai-image-checker:v1.0 .
```

### 2. Push to registry:
```bash
docker tag ai-image-checker:v1.0 your-registry/ai-image-checker:v1.0
docker push your-registry/ai-image-checker:v1.0
```

### 3. Deploy with orchestration:
- Kubernetes: Create deployment and service manifests
- Docker Swarm: Use `docker stack deploy`
- AWS ECS/Fargate: Use task definitions

### 4. Enable HTTPS:
Use a reverse proxy (nginx, traefik, caddy) in front of the container.

## Health Checks

The container includes health checks:
- Endpoint: `http://localhost:8000/health`
- Interval: 30 seconds
- Timeout: 10 seconds
- Start period: 5 minutes (allows models to load)

## Environment Variables

Set in `docker-compose.yml`:

```yaml
environment:
  - CUDA_VISIBLE_DEVICES=0,1  # Use GPUs 0 and 1
  - HF_HOME=/app/.cache/huggingface
  - TRANSFORMERS_CACHE=/app/.cache/huggingface
```

## Monitoring

### Check container stats:
```bash
docker stats ai-image-checker
```

### View resource usage:
```bash
docker-compose top
```

## Backup Model Cache

```bash
# Create backup
docker run --rm -v ai_image_checker_huggingface-cache:/data -v $(pwd):/backup alpine tar czf /backup/models-backup.tar.gz -C /data .

# Restore backup
docker run --rm -v ai_image_checker_huggingface-cache:/data -v $(pwd):/backup alpine tar xzf /backup/models-backup.tar.gz -C /data
```

## Multi-Stage Builds (Advanced)

For smaller production images, consider multi-stage builds:
- Build stage: Compile dependencies
- Runtime stage: Copy only needed files

## Security Best Practices

1. **Don't run as root:**
   Add to Dockerfile:
   ```dockerfile
   RUN useradd -m -u 1000 appuser
   USER appuser
   ```

2. **Scan for vulnerabilities:**
   ```bash
   docker scan ai-image-checker
   ```

3. **Use specific base image versions:**
   ```dockerfile
   FROM python:3.11.7-slim
   ```

4. **Minimize image layers**
5. **Don't include secrets in image**

## Next Steps

- Set up CI/CD pipeline for automated builds
- Configure monitoring (Prometheus, Grafana)
- Set up log aggregation (ELK stack, Loki)
- Implement rate limiting and authentication
- Scale horizontally with load balancer
