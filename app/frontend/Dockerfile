FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    nginx \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=appuser:appuser app.py .
COPY --chown=appuser:appuser pages/ ./pages/
COPY --chown=appuser:appuser utils/ ./utils/
COPY --chown=appuser:appuser components/ ./components/

# Create .streamlit directory for config
RUN mkdir -p /app/.streamlit && chown -R appuser:appuser /app/.streamlit

# Create Streamlit config
COPY --chown=appuser:appuser .streamlit/config.toml /app/.streamlit/config.toml
COPY --chown=appuser:appuser nginx.conf /app/nginx.conf
COPY --chown=appuser:appuser start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Set environment variables
ENV PORT=8501 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STREAMLIT_SERVER_PORT=8502 \
    STREAMLIT_SERVER_HEADLESS=true

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Run nginx proxy + Streamlit
CMD ["/app/start.sh"]
