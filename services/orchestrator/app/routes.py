"""Orchestrator HTTP surface: start/resume a workflow, report readiness, resolve items.

Start/resume enqueue an IDEMPOTENT durable DB event (keyed by enquiry + revision); they
never run the graph inline. Readiness reports which required handlers are still missing,
so production stays not-ready until the full specialist set is registered (prompt 09).
The module-level ``router`` is a prefix-free parent that mounts the public ``/v1/workflow``
routes and the token-guarded ``/internal`` routes, so main.py keeps including one router.
Internal routes use the internal service token and the propagated actor context (F17).
"""
from __future__ import annotations

import hmac
import os
from uuid import UUID

from fastapi import APIRouter, Header, Request

from app.features.f17_multi_part_enquiries import F17Request, F17Result, resolve_items
from app.features.f38_correct_extracted_details import F38Request, F38Result, correct_extraction
from app.handlers import missing_handlers
from partsiq_common.contracts import ActorContext, Contract, RevisionRequest
from partsiq_common.errors import PartsIQError

router = APIRouter()  # prefix-free parent imported by main.py
workflow_router = APIRouter(prefix="/v1/workflow", tags=["workflow"])
internal_router = APIRouter(prefix="/internal", tags=["internal"])

_INTERNAL_TOKEN_ENV = "INTERNAL_SERVICE_TOKEN"


def verify_internal_token(provided: str | None) -> None:
    """Constant-time check of the internal service token; unconfigured means local dev/tests."""
    expected = os.environ.get(_INTERNAL_TOKEN_ENV)
    if not expected:
        return
    if not provided or not hmac.compare_digest(provided, expected):
        raise PartsIQError("UNAUTHENTICATED", internal_detail="missing or invalid internal service token")


class ResolveItemsBody(Contract):
    """Internal call body: the gateway-verified actor context plus the typed F17 request."""

    actor: ActorContext
    request: F17Request


class CorrectEnquiryBody(Contract):
    """Internal call body: the gateway-verified actor context plus the typed correction (F38)."""

    actor: ActorContext
    change: RevisionRequest


@workflow_router.get("/readiness")
async def readiness(request: Request) -> dict:
    handlers = getattr(request.app.state, "handlers", None)
    missing = missing_handlers(handlers)
    return {"ready": not missing, "missing_handlers": missing}


@workflow_router.post("/{enquiry_id}/start", status_code=202)
async def start(request: Request, enquiry_id: UUID) -> dict:
    enqueue = request.app.state.enqueue_event
    event_id = await enqueue(enquiry_id, "start")
    return {"event_id": str(event_id)}


@workflow_router.post("/{enquiry_id}/resume", status_code=202)
async def resume(request: Request, enquiry_id: UUID) -> dict:
    enqueue = request.app.state.enqueue_event
    event_id = await enqueue(enquiry_id, "resume")
    return {"event_id": str(event_id)}


@internal_router.post("/items/resolve", response_model=None)
async def resolve_items_route(
    request: Request,
    body: ResolveItemsBody,
    x_internal_token: str | None = Header(default=None),
) -> F17Result:
    """Resolve an enquiry's items (F17). The live planning store is injected at startup (BLOCKED here)."""
    verify_internal_token(x_internal_token)
    store = getattr(request.app.state, "item_planning_store", None)
    if store is None:
        raise PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail="item planning store not configured")
    return await resolve_items(body.actor, body.request, store=store)


@internal_router.post("/enquiries/correct", response_model=None)
async def correct_enquiry_route(
    request: Request,
    body: CorrectEnquiryBody,
    x_internal_token: str | None = Header(default=None),
) -> F38Result:
    """Apply typed extracted-detail corrections (F38). The revision store is injected (BLOCKED here)."""
    verify_internal_token(x_internal_token)
    repo = getattr(request.app.state, "revision_repo", None)
    if repo is None:
        raise PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail="revision store not configured")
    return await correct_extraction(body.actor, F38Request(change=body.change), repo=repo)


router.include_router(workflow_router)
router.include_router(internal_router)
