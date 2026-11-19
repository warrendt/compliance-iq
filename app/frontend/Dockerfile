# ComplianceIQ frontend: nginx (port 8501) reverse-proxying Streamlit (8502).
ARG PYTHON_IMAGE=python:3.14-slim-trixie
FROM ${PYTHON_IMAGE}

# nginx mainline from the official nginx.org repo (Debian's package lags the
# upstream security releases). Signing key fingerprint is verified per
# https://nginx.org/en/linux_packages.html#Debian
ARG NGINX_KEY_FINGERPRINT=573BFD6B3D8FBC641079A6ABABF5BD827BD9BF62

WORKDIR /app

RUN set -eux; \
    apt-get update; \
    apt-get upgrade -y --no-install-recommends; \
    apt-get install -y --no-install-recommends ca-certificates curl gnupg2; \
    export GNUPGHOME="$(mktemp -d)"; \
    curl -fsSL https://nginx.org/keys/nginx_signing.key \
        | gpg --dearmor -o /usr/share/keyrings/nginx-archive-keyring.gpg; \
    gpg --dry-run --quiet --no-keyring --import --import-options import-show \
        /usr/share/keyrings/nginx-archive-keyring.gpg | grep -q "${NGINX_KEY_FINGERPRINT}"; \
    rm -rf "${GNUPGHOME}"; \
    . /etc/os-release; \
    echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] https://nginx.org/packages/mainline/debian ${VERSION_CODENAME} nginx" \
        > /etc/apt/sources.list.d/nginx.list; \
    printf 'Package: *\nPin: origin nginx.org\nPin: release o=nginx\nPin-Priority: 900\n' \
        > /etc/apt/preferences.d/99nginx; \
    apt-get update; \
    apt-get install -y --no-install-recommends nginx; \
    apt-get purge -y --auto-remove gnupg2; \
    rm -rf /var/lib/apt/lists/*; \
    nginx -v

RUN useradd -m -u 1000 appuser && \
    mkdir -p /var/cache/nginx /var/log/nginx && \
    chown -R appuser:appuser /app /var/cache/nginx /var/log/nginx

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip==26.3 && \
    pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser app.py .
COPY --chown=appuser:appuser pages/ ./pages/
COPY --chown=appuser:appuser utils/ ./utils/
COPY --chown=appuser:appuser components/ ./components/
COPY --chown=appuser:appuser assets/ ./assets/
COPY --chown=appuser:appuser .streamlit/config.toml /app/.streamlit/config.toml
COPY --chown=appuser:appuser nginx.conf /app/nginx.conf
COPY --chown=appuser:appuser start.sh /app/start.sh
RUN sed -i 's/\r$//' /app/start.sh && chmod +x /app/start.sh

ENV PORT=8501 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STREAMLIT_SERVER_PORT=8502 \
    STREAMLIT_SERVER_HEADLESS=true

USER appuser

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

CMD ["/app/start.sh"]
