"""Orchestrator HTTP surface: start/resume a workflow and report readiness.

Start/resume enqueue an IDEMPOTENT durable DB event (keyed by enquiry + revision); they
never run the graph inline. Readiness reports which required handlers are still missing,
so production stays not-ready until the full specialist set is registered (prompt 09).
Internal-token protected; event enqueue + consumer live behind app.state.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request

from app.handlers import missing_handlers

router = APIRouter(prefix="/v1/workflow", tags=["workflow"])


@router.get("/readiness")
async def readiness(request: Request) -> dict:
    handlers = getattr(request.app.state, "handlers", None)
    missing = missing_handlers(handlers)
    return {"ready": not missing, "missing_handlers": missing}


@router.post("/{enquiry_id}/start", status_code=202)
async def start(request: Request, enquiry_id: UUID) -> dict:
    enqueue = request.app.state.enqueue_event
    event_id = await enqueue(enquiry_id, "start")
    return {"event_id": str(event_id)}


@router.post("/{enquiry_id}/resume", status_code=202)
async def resume(request: Request, enquiry_id: UUID) -> dict:
    enqueue = request.app.state.enqueue_event
    event_id = await enqueue(enquiry_id, "resume")
    return {"event_id": str(event_id)}
