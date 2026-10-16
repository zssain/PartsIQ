"""Worker service entry point (prompt 15).

A durable job worker: it consumes jobs from Redis that were persisted first in Postgres,
runs them under a fenced lease, and writes workflow events — it never calls the
orchestrator over HTTP. The only HTTP surface is the internal signing route, reachable on
the Docker network behind the internal service token. Readiness stays false until the job
store, queue and Storage backend are wired at startup; the live adapters are integration
work, so this process is not runnable end-to-end offline (reported, not faked).
"""
from __future__ import annotations

from fastapi import FastAPI

from app.internal import router as internal_router
from partsiq_common.app_factory import create_service_app
from partsiq_common.config import BaseServiceSettings

__version__ = "0.1.0"

settings = BaseServiceSettings(service_name="partsiq-worker")


async def on_startup(app: FastAPI) -> None:
    # Live job store / Redis queue / Storage backend are wired here from the DB pool and
    # Storage credential; left unset offline so readiness is honestly false.
    app.state.store = getattr(app.state, "store", None)
    app.state.queue = getattr(app.state, "queue", None)
    app.state.storage_backend = getattr(app.state, "storage_backend", None)
    app.state.resolve_key = getattr(app.state, "resolve_key", None)
    app.state.worker_ready = app.state.store is not None and app.state.queue is not None


app = create_service_app(
    settings,
    title="PartsIQ Worker",
    version=__version__,
    routers=[internal_router],
    requires_database=True,
    requires_redis=True,
    on_startup=on_startup,
)
