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


# The completed feature api modules, in feature order. Each exposes ``router = APIRouter()``
# with the exact method/path/response_model/status from ``spec/endpoints.json`` and delegates to
# its ``features/fNN_*`` facade. A module is listed here ONLY once it exists end-to-end — an
# unfinished feature is never imported, so a half-built feature cannot break application startup
# (prompt 01 step 8). Later prompts append their module here as each feature lands.
_COMPLETED_FEATURE_MODULES: tuple[str, ...] = (
    "partsiq.api.f02_demo_scenarios_and_assets",
    "partsiq.api.f04_demo_isolation",
    "partsiq.api.f05_demo_reset",
    "partsiq.api.f09_bilingual_chat",
    "partsiq.api.f10_structured_extraction",
    "partsiq.api.f11_clarifying_questions",
    "partsiq.api.f12_conversation_memory",
    "partsiq.api.f13_private_uploads",
    "partsiq.api.f18_progress_timeline",
    "partsiq.api.f19_enquiry_history",
)

_FEATURES_INCLUDED = False


def include_completed_features() -> None:
    """Import the completed feature api modules and include their routers additively.

    Idempotent: a second call is a no-op so re-creating the app (e.g. per test) does not mount a
    route twice. Each module's ``router`` is attached to the shared ``/v1`` router via
    :func:`register_feature_router`. Called once from ``create_app`` in ``main.py``.
    """
    global _FEATURES_INCLUDED
    if _FEATURES_INCLUDED:
        return
    import importlib

    for module_path in _COMPLETED_FEATURE_MODULES:
        module = importlib.import_module(module_path)
        register_feature_router(module.router)
    _FEATURES_INCLUDED = True
