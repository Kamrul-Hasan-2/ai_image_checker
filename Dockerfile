# Use Python 3.11 base image
FROM python:3.11-slim

WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    TRANSFORMERS_CACHE=/root/.cache/huggingface \
    TORCH_HOME=/root/.cache/torch

# Install system dependencies in one layer
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgomp1 \
    libgl1 \
    libsm6 \
    libxext6 \
    libxrender1 \
    curl && \
    rm -rf /var/lib/apt/lists/*

# Copy and install dependencies
COPY requirements.txt .

# Install PyTorch CPU version first
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Install other dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
