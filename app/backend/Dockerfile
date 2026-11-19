# syntax=docker/dockerfile:1
# Backend API image.
#
# Built on the official slim Python image. The previous base
# (mcr.microsoft.com/devcontainers/python) is a development image: it ships
# git, compilers and a `vscode` user with passwordless sudo, so any code
# execution in the API was one `sudo` away from root.

ARG PYTHON_IMAGE=python:3.14-slim-trixie

FROM ${PYTHON_IMAGE} AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH

COPY requirements.txt .
RUN pip install --upgrade pip==26.3 \
    && pip install -r requirements.txt

FROM ${PYTHON_IMAGE}

# Pick up Debian security fixes released after the base image was published.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10001 --create-home --shell /usr/sbin/nologin appuser

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
# Application code stays root-owned so the runtime user cannot modify it.
COPY app/ ./app/
RUN test -d /app/app/pipeline

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health/ping')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
