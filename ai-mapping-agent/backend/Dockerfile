# Multi-stage build for smaller image size
# Use MCR devcontainer image to avoid Docker Hub dependency
FROM mcr.microsoft.com/devcontainers/python:3.11 as builder

# Set working directory
WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Final stage
FROM mcr.microsoft.com/devcontainers/python:3.11

# Set working directory
WORKDIR /app
# Copy Python dependencies from builder
COPY --from=builder /root/.local /home/vscode/.local

# Copy application code
COPY app/ ./app/

# Ensure pipeline package is available
RUN test -d /app/app/pipeline && echo 'Pipeline package present' || echo 'WARNING: pipeline package missing'

# Set environment variables
ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Switch to non-root user (provided by devcontainer base)
USER vscode

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health/ping')"

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
