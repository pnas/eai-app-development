# syntax=docker/dockerfile:1
# Podman / Docker Multi-stage Containerfile for Decoupled Streamlit Retrieval Agent

# Base Stage: Python 3.12 with all dependencies installed
FROM python:3.12-slim AS base

WORKDIR /app

# Prevent Python from writing .pyc files and enable unbuffered terminal logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    RESOURCES_DIR=/app/docs/resources

# Install curl for reliable container healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency definition and install packages
COPY python/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy Python codebase and regulatory documents
COPY python/src /app/src
COPY docs/resources /app/docs/resources

# -------------------------------------------------------------
# Stage 1: backend (FastAPI SSE Agent Microservice)
# -------------------------------------------------------------
FROM base AS backend

ENV AGENT_MOCK_MODE=true

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.langchain_suite.frontend_agent.backend.server:app", "--host", "0.0.0.0", "--port", "8000"]

# -------------------------------------------------------------
# Stage 2: frontend (Streamlit Web Interface)
# -------------------------------------------------------------
FROM base AS frontend

ENV STREAMLIT_AGENT_MODE=remote \
    AGENT_BACKEND_URL=http://backend:8000 \
    AGENT_DEFAULT_PROVIDER=mock \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

EXPOSE 8501

HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "src/langchain_suite/frontend_agent/frontend/app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
