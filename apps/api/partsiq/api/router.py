"""The single public API router mounted under ``/v1`` (foundation 01).

Feature routers created by later prompts are included here additively via
:func:`register_feature_router`. Unfinished feature modules are never imported, so a
half-built feature cannot break application startup (prompt 01 step 8).
"""
from __future__ import annotations

from fastapi import APIRouter

v1_router = APIRouter(prefix="/v1")


@v1_router.get("/meta", tags=["meta"], summary="Non-privileged API metadata")
async def api_meta() -> dict[str, str | bool]:
    """Public, credit-free metadata. Confirms the API surface is reachable."""
    return {"api": "partsiq", "version": "v1", "public": True}


def register_feature_router(router: APIRouter) -> None:
    """Attach a completed feature router to the public ``/v1`` surface."""
    v1_router.include_router(router)
