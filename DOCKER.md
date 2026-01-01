# Docker Setup for AI Image Checker

## Build the Docker Image

```bash
docker build -t kamrulhasan00/ai_image_checker:latest .
```

## Run the Container

### Basic Run (CPU only)
```bash
docker run -d -p 8000:8000 --name ai_image_checker kamrulhasan00/ai_image_checker:latest
```

### Run with GPU Support (if you have NVIDIA GPU)
```bash
docker run -d -p 8000:8000 --gpus all --name ai_image_checker kamrulhasan00/ai_image_checker:latest
```

### Run with Volume Mount (to persist model cache)
```bash
docker run -d -p 8000:8000 \
  -v %cd%/model_cache:/root/.cache/huggingface \
  --name ai_image_checker \
  kamrulhasan00/ai_image_checker:latest
```

## Manage Container

### Check container status
```bash
docker ps
```

### View logs
```bash
docker logs ai_image_checker
docker logs -f ai_image_checker  # Follow logs in real-time
```

### Stop container
```bash
docker stop ai_image_checker
```

### Start container
```bash
docker start ai_image_checker
```

### Remove container
```bash
docker rm -f ai_image_checker
```

## Push to Docker Hub

1. Login to Docker Hub:
```bash
docker login -u kamrulhasan00
```

2. Push the image:
```bash
docker push kamrulhasan00/ai_image_checker:latest
```

## Pull and Run from Docker Hub (on any machine)

```bash
docker pull kamrulhasan00/ai_image_checker:latest
docker run -d -p 8000:8000 --name ai_image_checker kamrulhasan00/ai_image_checker:latest
```

## Test the API

Once the container is running, test it:

```bash
# Health check
curl http://localhost:8000/health

# API test
curl -X POST http://localhost:8000/api/ai_check_detection \
  -H "Content-Type: application/json" \
  -d '{\"image_url\": \"https://example.com/image.jpg\", \"category\": \"Electronics\"}'
```

## Troubleshooting

### Container won't start
- Check logs: `docker logs ai_image_checker`
- Check if port 8000 is already in use: `netstat -ano | findstr :8000`

### Out of memory
The container needs at least 8GB RAM for all models. To reduce memory:
- Edit main.py to disable Qwen7B (already disabled by default)
- Use smaller models

### Slow startup
First startup takes 2-3 minutes to load all AI models. This is normal.
