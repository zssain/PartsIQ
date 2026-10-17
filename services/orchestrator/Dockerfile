# Orchestrator image (prompt 24). Base pinned by digest from infra/images.lock.json
# (re-verify against the registry at deploy). Runs the durable LangGraph workflow service;
# the event-consumer is the SAME image with a different command (see docker-compose.prod.yml).
# Build context: repository root.
FROM python:3.12-slim@sha256:0000000000000000000000000000000000000000000000000000000000000001

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN useradd --create-home --uid 10001 appuser

WORKDIR /app

COPY libs/partsiq_common /tmp/partsiq_common
RUN pip install /tmp/partsiq_common && rm -rf /tmp/partsiq_common

COPY services/orchestrator/pyproject.toml ./pyproject.toml
RUN pip install langgraph==1.1.3 langgraph-checkpoint-postgres==3.0.4

COPY services/orchestrator/app ./app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 \
    CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/v1/workflow/readiness', timeout=2).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
