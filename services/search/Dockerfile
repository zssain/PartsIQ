# Build context: repository root. Set INSTALL_EMBEDDINGS=true to enable semantic search.
FROM python:3.12-slim

ARG INSTALL_EMBEDDINGS=false

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /home/appuser/.cache \
    && chown appuser:appuser /home/appuser/.cache

WORKDIR /app

COPY libs/partsiq_common /tmp/partsiq_common
RUN pip install /tmp/partsiq_common && rm -rf /tmp/partsiq_common

COPY services/search/requirements-embeddings.txt ./requirements-embeddings.txt
RUN if [ "$INSTALL_EMBEDDINGS" = "true" ]; then pip install -r requirements-embeddings.txt; fi

COPY services/search/app ./app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=3 \
    CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=2).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
