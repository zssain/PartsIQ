# Build context: repository root. Set INSTALL_EMBEDDINGS=true to enable the "embed" command.
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

COPY tools/catalog/requirements-embeddings.txt ./requirements-embeddings.txt
RUN if [ "$INSTALL_EMBEDDINGS" = "true" ]; then pip install -r requirements-embeddings.txt; fi

COPY tools/catalog/catalog ./catalog

USER appuser

ENTRYPOINT ["python", "-m", "catalog"]
CMD ["--help"]
