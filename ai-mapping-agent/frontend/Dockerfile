FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
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
RUN echo "[server]\n\
port = 8501\n\
address = \"0.0.0.0\"\n\
headless = true\n\
enableCORS = false\n\
enableXsrfProtection = true\n\
maxUploadSize = 50\n\
\n\
[browser]\n\
gatherUsageStats = false\n\
serverAddress = \"0.0.0.0\"\n\
\n\
[theme]\n\
primaryColor = \"#0078D4\"\n\
backgroundColor = \"#FFFFFF\"\n\
secondaryBackgroundColor = \"#F5F5F5\"\n\
textColor = \"#262730\"\n\
" > /app/.streamlit/config.toml

# Set environment variables
ENV PORT=8501 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_HEADLESS=true

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Run Streamlit
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
