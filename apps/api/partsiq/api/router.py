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
    "partsiq.api.f14_nameplate_ocr",
    "partsiq.api.f15_ocr_confirmation",
    "partsiq.api.f16_photo_quality_feedback",
    "partsiq.api.f17_multi_part_enquiries",
    "partsiq.api.f18_progress_timeline",
    "partsiq.api.f19_enquiry_history",
    "partsiq.api.f20_machine_identification",
    "partsiq.api.f21_machine_mismatch_detection",
    "partsiq.api.f22_compatibility_gate",
    "partsiq.api.f23_aliases_and_typo_matching",
    "partsiq.api.f24_semantic_retrieval",
    "partsiq.api.f25_ranked_candidates",
    "partsiq.api.f26_ambiguity_handling",
    "partsiq.api.f27_match_explanations",
    "partsiq.api.f28_compatibility_references",
    "partsiq.api.f30_old_part_numbers",
    "partsiq.api.f31_candidate_comparison",
    "partsiq.api.f32_warehouse_stock",
    "partsiq.api.f33_fulfilment_planning",
    "partsiq.api.f34_transfer_estimates",
    "partsiq.api.f35_stock_freshness",
    "partsiq.api.f36_staff_inbox",
    "partsiq.api.f37_review_workspace",
    "partsiq.api.f39_review_actions",
    "partsiq.api.f41_internal_notes",
    "partsiq.api.f42_assignments",
    "partsiq.api.f43_overdue_indicators",
    "partsiq.api.f47_human_publication_gate",
    "partsiq.api.f49_audit_trail",
    "partsiq.api.f57_catalogue_browser",
    # Review/workflow extras, catalogue-ops, analytics/eval/observability.
    "partsiq.api.f38_correct_extracted_details",
    "partsiq.api.f40_approval_invalidation",
    "partsiq.api.f44_conversation_summary",
    "partsiq.api.f45_reply_drafting",
    "partsiq.api.f46_verification_gate",
    "partsiq.api.f50_durable_workflows",
    "partsiq.api.f51_background_jobs",
    "partsiq.api.f52_retry_and_dedup",
    "partsiq.api.f54_access_and_permissions",
    "partsiq.api.f55_saved_machines",
    "partsiq.api.f56_repeat_enquiry",
    "partsiq.api.f58_catalogue_imports",
    "partsiq.api.f59_catalogue_versioning",
    "partsiq.api.f60_missing_parts_queue",
    "partsiq.api.f61_enquiry_pdf",
    "partsiq.api.f62_labelled_evaluations",
    "partsiq.api.f63_metrics_dashboard",
    "partsiq.api.f64_latency_and_ai_cost",
    "partsiq.api.f65_correction_feedback",
    "partsiq.api.f67_traces",
    # Demo-journey loop closers (timeline + in-demo review approval) over the fixture journey.
    "partsiq.api.demo_journey",
    # Workspace runtime (ADR 0002): runs, exchanges, commands, composed reads and admin.
    "partsiq.api.workspace_api",
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
