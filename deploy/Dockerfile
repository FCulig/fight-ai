# syntax=docker/dockerfile:1
# The production backend image: FastAPI, the SPA it serves, and a slim ai/
# interpreter for upload validation and migrations. deploy.sh builds it on the
# server (arm64), with the repo root as the build context.

FROM node:24-slim AS frontend
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Two interpreters, as in dev: the backend's own, and a slim ai/ one without
# torch that runs the upload validator, the video metadata probe and Alembic.
COPY backend/requirements.txt /tmp/req/backend.txt
RUN python -m venv /opt/venv-backend \
 && /opt/venv-backend/bin/pip install -r /tmp/req/backend.txt
COPY db/requirements.txt /tmp/req/db.txt
COPY deploy/requirements-ai-server.txt /tmp/req/ai-server.txt
RUN python -m venv /opt/venv-ai \
 && /opt/venv-ai/bin/pip install -r /tmp/req/db.txt -r /tmp/req/ai-server.txt

RUN useradd --create-home --uid 1000 app
COPY --chown=app:app backend/ /app/backend/
COPY --chown=app:app ai/ /app/ai/
COPY --chown=app:app db/ /app/db/
COPY --from=frontend --chown=app:app /src/dist/ /app/frontend/dist/

# The server never runs the pipeline: the validator leaves uploads queued for a
# worker (PIPELINE_DISPATCH=queue). VIDEO_BASE_DIR must equal AI_DIR, because
# the validator and the metadata probe resolve stored relative paths from AI_DIR.
ENV PATH=/opt/venv-backend/bin:$PATH \
    FRONTEND_DIST=/app/frontend/dist \
    AI_DIR=/app/ai \
    AI_PYTHON=/opt/venv-ai/bin/python \
    VIDEO_BASE_DIR=/app/ai \
    PIPELINE_DISPATCH=queue

USER app
WORKDIR /app/backend
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/', timeout=4)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
