"""Orchestrator service entry point.

Durable workflow service. Readiness stays FALSE until every specialist handler is
registered (prompts 10-14) — we never ship fake-success nodes. The Postgres checkpointer
is built from the DB pool at startup; checkpoint DDL is applied only by prompt 03, never
under the runtime role.
"""
from __future__ import annotations

from fastapi import FastAPI

from partsiq_common.app_factory import create_service_app
from partsiq_common.config import BaseServiceSettings

from app import __version__
from app.handlers import WorkflowHandlers, is_ready
from app.routes import router

settings = BaseServiceSettings(service_name="partsiq-orchestrator")

# Registered by later prompts (10-14); None here keeps readiness false by design.
HANDLERS: WorkflowHandlers | None = None


async def on_startup(app: FastAPI) -> None:
    app.state.handlers = HANDLERS
    app.state.workflow_ready = is_ready(HANDLERS)


app = create_service_app(
    settings,
    title="PartsIQ Orchestrator",
    version=__version__,
    routers=[router],
    requires_database=True,
    on_startup=on_startup,
)
