# =====================================================================
# Sprawler - Production Dockerfile (Playwright + Chromium + Tesseract OCR)
# =====================================================================

FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy AS base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system dependencies: Tesseract OCR (with Persian and English trained data)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-fas \
    tesseract-ocr-eng \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements, local wheels, and install python packages
COPY requirements.txt .
COPY wheels/ /app/wheels/
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install \
    --find-links=/app/wheels \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --default-timeout 180 \
    --retries 10 \
    -r requirements.txt

# Ensure Chromium browser binary is present
RUN playwright install chromium

# Copy application source code and tests
COPY src/ /app/src/
COPY tests/ /app/tests/

# Prepare data directory and setup non-root user permissions
RUN mkdir -p /app/data && chown -R pwuser:pwuser /app

# Run as non-root user (pwuser is provided by playwright base image)
USER pwuser

# Healthcheck targeting FastAPI /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# Run FastAPI server with Uvicorn
CMD ["uvicorn", "crawler.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
