# PartsIQ single application image (prompt 24 — single-workflow edition).
#
# ONE immutable CPU-only image runs BOTH roles from the same `partsiq` package:
#   * API     -> uvicorn partsiq.main:create_app --factory --host 0.0.0.0 --port 8000 --workers 1
#   * worker  -> python -m partsiq.jobs.main
# The two roles differ ONLY by the container `command` (see infra/compose.*.yml); the image
# itself is identical, so a single release SHA pins both. The guided workflow uses LangGraph
# (ADR 0002); there is no other agent framework. The API never imports the optional encoder; the
# optional sentence-transformers + CPU torch wheel are loaded by the worker only and are
# NOT baked into this base image (see the semantic profile in infra/compose.production.yml).
#
# Base is pinned by @sha256 digest from spec/images.lock.json — RE-VERIFY against the live
# registry at deploy time (prompt 26/27) with `docker buildx imagetools inspect`; pins are
# recorded, not proven against a live registry here (BLOCKED — no Docker/registry access).
# Build context: repository root.

# ---- Stage 1: build the frozen dependency environment -----------------------------------
FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Frozen Python dependencies (exact pins). Installed into an isolated prefix that is copied
# into the runtime stage, so build tooling never ships in the final image.
COPY spec/python-requirements.lock ./python-requirements.lock
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r python-requirements.lock

# ---- Stage 2: minimal runtime -----------------------------------------------------------
FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app"

# Non-root runtime user (implementation step 9).
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser

WORKDIR /app

# Frozen environment from the build stage.
COPY --from=builder /opt/venv /opt/venv

# The single `partsiq` package (API factory + worker entrypoint live here).
COPY apps/api/partsiq ./partsiq
# Bundled OFL fonts + logo for the PDF export (read locally by Chromium; no network).
COPY apps/web/public/brand ./brand
# Headless Chromium for the export_pdf worker job, at a fixed path readable by appuser.
# --only-shell installs the small headless shell (not full Chrome); --with-deps adds its libs.
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright
RUN playwright install --with-deps --only-shell chromium \
    && rm -rf /var/lib/apt/lists/* \
    && chmod -R o+rx /opt/ms-playwright
# The pinned dependency manifest for the in-image healthcheck/readiness tooling.
COPY tools/healthcheck.py ./tools/healthcheck.py

USER appuser

EXPOSE 8000

# Liveness probe spends NO provider credits; it only hits the local /health route. The API
# container overrides nothing; worker containers disable this in compose (no HTTP port).
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
    CMD ["python", "/app/tools/healthcheck.py"]

# Default command is the API; the worker command is set in compose (python -m partsiq.jobs.main).
CMD ["uvicorn", "partsiq.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
