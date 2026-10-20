"""Workspace HTTP surface (ADR 0002): runs, exchanges, commands, pending actions, composed reads,
uploads and administration. Contracts are documented in docs/API_WORKSPACE.md.

Conventions shared with the rest of /v1:
* every route resolves a VERIFIED actor (demo token or Supabase bearer) — 401 otherwise;
* resources outside the caller's workspace/scope are 404; a missing capability is 403;
* every mutation requires an ``Idempotency-Key`` and an expected revision/state version where it
  changes enquiry state — a stale value is 409; invalid input is 422; limits are 429; unavailable
  dependencies are 503 with a request id and no internal detail.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer, get_container, idempotency_key, require_actor
from partsiq.core.errors import PartsIQError

router = APIRouter(tags=["workspace"])

_SAMPLE_PLATE = Path(__file__).resolve().parents[4] / "fixtures" / "nameplates" / "Corvane_Air_CA-110_800000.png"


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StartRun(_Body):
    mode: Literal["guided", "collaboration"]
    expected_revision: int = Field(ge=1)


class RunCommand(_Body):
    type: Literal["pause", "resume", "cancel", "instruct", "answer", "confirm_nameplate", "resolve_delegation", "fixture_replay"]
    expected_revision: int = Field(ge=1)
    expected_state_version: int | None = Field(default=None, ge=1)
    payload: dict[str, Any] = Field(default_factory=dict)


class InviteMember(_Body):
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    display_name: str | None = Field(default=None, max_length=120)
    roles: list[Literal["reviewer", "catalogue_admin", "admin"]] = Field(default_factory=list, max_length=3)


class SetRoles(_Body):
    roles: list[Literal["reviewer", "catalogue_admin", "admin"]] = Field(max_length=3)
    expected_version: int = Field(ge=1)


async def _json(request: Request, model: type[_Body]) -> Any:
    raw = await request.body()
    if not raw:
        raise PartsIQError("MALFORMED_REQUEST", internal_detail="request body is required")
    try:
        return model.model_validate_json(raw)
    except ValidationError as exc:
        raise PartsIQError("VALIDATION_FAILED", detail="One or more fields are invalid.") from exc


def runtime(container: AppContainer = Depends(get_container)) -> Any:
    service = getattr(container, "runtime", None)
    if service is None:
        raise PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail="workspace runtime not configured")
    return service


# ----------------------------------------------------------------------------- reads


@router.get("/workspace/status", summary="Execution modes and dependency availability (no secrets)")
async def status(actor: ActorContext = Depends(require_actor), service: Any = Depends(runtime)) -> dict[str, Any]:
    return {**service.execution_status(), "dependencies": service.dependency_status(), "limits": service.limits.as_dict()}


@router.get("/workspace/dashboard", summary="Role-aware dashboard counts for the caller's scope")
async def dashboard(actor: ActorContext = Depends(require_actor), service: Any = Depends(runtime)) -> dict[str, Any]:
    return await service.dashboard(actor)


@router.get("/workspace/enquiries", summary="Search the caller's enquiries (own or review scope)")
async def search_enquiries(
    scope: Literal["own", "review"] = "own",
    status: str | None = Query(default=None, max_length=120),
    q: str | None = Query(default=None, max_length=200),
    mode: Literal["guided", "collaboration"] | None = None,
    assigned: Literal["me", "none"] | None = None,
    overdue: bool = False,
    cursor: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    actor: ActorContext = Depends(require_actor),
    service: Any = Depends(runtime),
) -> dict[str, Any]:
    return await service.search_enquiries(actor, scope=scope, status=status, query=q, cursor=cursor, limit=limit, mode=mode, assigned=assigned, overdue=overdue)


@router.get("/warehouses", summary="Supported destination warehouses")
async def warehouses(actor: ActorContext = Depends(require_actor), service: Any = Depends(runtime)) -> list[dict[str, Any]]:
    return await service.warehouses(actor)


@router.get("/enquiries/{enquiry_id}/detail", summary="Composed enquiry detail (customer-safe; reviewer fields only in scope)")
async def enquiry_detail(enquiry_id: UUID, actor: ActorContext = Depends(require_actor), service: Any = Depends(runtime)) -> dict[str, Any]:
    return await service.enquiry_detail(actor, enquiry_id)


@router.get("/staff/enquiries/{enquiry_id}/detail", summary="Composed review read: evidence, draft, notes, history")
async def review_detail(enquiry_id: UUID, actor: ActorContext = Depends(require_actor), service: Any = Depends(runtime)) -> dict[str, Any]:
    return await service.review_detail(actor, enquiry_id)


@router.get("/enquiries/{enquiry_id}/pending", summary="Open pending actions (clarification / consent / confirmation)")
async def pending(enquiry_id: UUID, actor: ActorContext = Depends(require_actor), service: Any = Depends(runtime)) -> list[dict[str, Any]]:
    return await service.list_pending(actor, enquiry_id)


# ----------------------------------------------------------------------------- runs


@router.get("/enquiries/{enquiry_id}/runs", summary="Runs for an enquiry (newest first; superseded runs kept)")
async def list_runs(enquiry_id: UUID, actor: ActorContext = Depends(require_actor), service: Any = Depends(runtime)) -> list[dict[str, Any]]:
    return await service.list_runs(actor, enquiry_id)


@router.post("/enquiries/{enquiry_id}/runs", status_code=202, summary="Start a new run in a chosen mode (never mutates an in-flight run)")
async def start_run(enquiry_id: UUID, request: Request, actor: ActorContext = Depends(require_actor), service: Any = Depends(runtime), key: UUID = Depends(idempotency_key)) -> dict[str, Any]:
    body: StartRun = await _json(request, StartRun)
    ws = await service.workspace(actor)
    replay = ws.idempotency.get(("start_run", key))
    if replay is not None:
        if replay[0] != body.model_dump_json():
            raise PartsIQError("IDEMPOTENCY_MISMATCH", detail="This idempotency key was used for a different request.")
        return await service.get_run(actor, UUID(replay[1]))
    view = await service.start_new_run(actor, enquiry_id, mode=body.mode, expected_revision=body.expected_revision)
    ws.idempotency[("start_run", key)] = (body.model_dump_json(), view["id"])
    return view


@router.get("/runs/{run_id}", summary="Run state, limits, usage, roster and open pending actions")
async def get_run(run_id: UUID, actor: ActorContext = Depends(require_actor), service: Any = Depends(runtime)) -> dict[str, Any]:
    return await service.get_run(actor, run_id)


@router.get("/runs/{run_id}/events", summary="Ordered exchanges after a sequence cursor (poll; no duplicates)")
async def run_events(run_id: UUID, after: int = Query(default=0, ge=0), limit: int = Query(default=100, ge=1, le=200), actor: ActorContext = Depends(require_actor), service: Any = Depends(runtime)) -> dict[str, Any]:
    return await service.run_events(actor, run_id, after=after, limit=limit)


@router.post("/runs/{run_id}/commands", status_code=202, summary="Pause / resume / cancel / instruct / answer / consent (server-enforced)")
async def run_command(run_id: UUID, request: Request, actor: ActorContext = Depends(require_actor), service: Any = Depends(runtime), key: UUID = Depends(idempotency_key)) -> dict[str, Any]:
    body: RunCommand = await _json(request, RunCommand)
    return await service.command(actor, run_id, body.model_dump(), key)


# ----------------------------------------------------------------------------- uploads


@router.post("/enquiries/{enquiry_id}/attachments", status_code=201, summary="Upload a nameplate photo (validated: type, magic bytes, size, pixels)")
async def upload_attachment(enquiry_id: UUID, request: Request, actor: ActorContext = Depends(require_actor), service: Any = Depends(runtime), key: UUID = Depends(idempotency_key)) -> dict[str, Any]:
    replay = await _upload_replay(service, actor, key)
    if replay is not None:
        return replay
    media_type = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    declared = int(request.headers.get("content-length") or 0)
    if declared > service.limits.max_upload_bytes:
        raise PartsIQError("PAYLOAD_TOO_LARGE", detail="The image is larger than the upload limit.")
    data = await request.body()
    attachment = await service.accept_upload(actor, enquiry_id, data=data, media_type=media_type, fixture_key=None)
    return await _upload_record(service, actor, key, attachment)


@router.post("/enquiries/{enquiry_id}/attachments/sample", status_code=201, summary="Attach the committed synthetic nameplate sample (demo)")
async def attach_sample(enquiry_id: UUID, actor: ActorContext = Depends(require_actor), service: Any = Depends(runtime), key: UUID = Depends(idempotency_key)) -> dict[str, Any]:
    replay = await _upload_replay(service, actor, key)
    if replay is not None:
        return replay
    if not _SAMPLE_PLATE.exists():
        raise PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail="sample nameplate fixture missing")
    attachment = await service.accept_upload(actor, enquiry_id, data=_SAMPLE_PLATE.read_bytes(), media_type="image/png", fixture_key=_SAMPLE_PLATE.name)
    return await _upload_record(service, actor, key, attachment)


async def _upload_replay(service: Any, actor: ActorContext, key: UUID) -> dict[str, Any] | None:
    ws = await service.workspace(actor)
    stored = ws.idempotency.get(("upload", key))
    return stored[1] if stored else None


async def _upload_record(service: Any, actor: ActorContext, key: UUID, attachment: Any) -> dict[str, Any]:
    ws = await service.workspace(actor)
    view = {"id": str(attachment.id), "status": attachment.status, "width": attachment.width, "height": attachment.height}
    ws.idempotency[("upload", key)] = ("upload", view)
    return view


# ----------------------------------------------------------------------------- catalogue


@router.get("/catalogue/search", summary="Search the active catalogue version (names, aliases, numbers)")
async def catalogue_search(
    q: str | None = Query(default=None, max_length=200),
    category: str | None = Query(default=None, max_length=60),
    model: str | None = Query(default=None, max_length=40),
    cursor: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
    actor: ActorContext = Depends(require_actor),
    service: Any = Depends(runtime),
) -> dict[str, Any]:
    return await service.catalogue_browse(actor, query=q, category=category, model_code=model, cursor=cursor, limit=limit)


@router.get("/catalogue/parts/{part_number}/detail", summary="Part detail: aliases, fitment evidence, supersession, stock")
async def catalogue_part(part_number: str, actor: ActorContext = Depends(require_actor), service: Any = Depends(runtime)) -> dict[str, Any]:
    if len(part_number) > 64:
        raise PartsIQError("VALIDATION_FAILED", detail="Part number is too long.")
    return await service.catalogue_part(actor, part_number)


@router.get("/machines/{machine_id}/check", summary="Re-validate a saved machine against the current catalogue")
async def machine_check(machine_id: UUID, actor: ActorContext = Depends(require_actor), service: Any = Depends(runtime)) -> dict[str, Any]:
    return await service.machine_check(actor, machine_id)


# ----------------------------------------------------------------------------- admin


@router.get("/admin/members", summary="Workspace members and roles (admin)")
async def members(actor: ActorContext = Depends(require_actor), service: Any = Depends(runtime)) -> dict[str, Any]:
    return await service.list_members(actor)


@router.post("/admin/members/invite", status_code=201, summary="Invite a member (Supabase invite link; synthetic in demo)")
async def invite(request: Request, actor: ActorContext = Depends(require_actor), service: Any = Depends(runtime), _key: UUID = Depends(idempotency_key)) -> dict[str, Any]:
    body: InviteMember = await _json(request, InviteMember)
    return await service.invite_member(actor, email=body.email, display_name=body.display_name, roles=list(body.roles))


@router.put("/admin/members/{member_id}/roles", summary="Change a member's roles (admin, audited, version-checked)")
async def set_roles(member_id: UUID, request: Request, actor: ActorContext = Depends(require_actor), service: Any = Depends(runtime), _key: UUID = Depends(idempotency_key)) -> dict[str, Any]:
    body: SetRoles = await _json(request, SetRoles)
    return await service.set_member_roles(actor, member_id, roles=list(body.roles), expected_version=body.expected_version)


@router.get("/admin/audit", summary="Append-only audit events (read-only, paginated)")
async def audit(
    action: str | None = Query(default=None, max_length=80),
    entity: str | None = Query(default=None, max_length=80),
    actor_id: str | None = Query(default=None, max_length=64),
    cursor: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    actor: ActorContext = Depends(require_actor),
    service: Any = Depends(runtime),
) -> dict[str, Any]:
    return await service.audit_search(actor, action=action, entity=entity, actor_id=actor_id, cursor=cursor, limit=limit)


@router.get("/admin/jobs", summary="Jobs and runs with status, retries and error category")
async def jobs(status: Literal["pending", "running", "succeeded", "failed", "cancelled"] | None = None, cursor: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=200), actor: ActorContext = Depends(require_actor), service: Any = Depends(runtime)) -> dict[str, Any]:
    return await service.list_jobs(actor, status=status, cursor=cursor, limit=limit)


@router.get("/admin/analytics", summary="Measured operational analytics (unmeasured values are null)")
async def analytics(actor: ActorContext = Depends(require_actor), service: Any = Depends(runtime)) -> dict[str, Any]:
    return await service.analytics_overview(actor)


@router.get("/admin/imports", summary="Import batches (catalogue admin)")
async def list_imports(actor: ActorContext = Depends(require_actor), service: Any = Depends(runtime)) -> list[dict[str, Any]]:
    return await service.list_imports(actor)


@router.put("/admin/imports/{import_id}/content", summary="Upload the CSV for a staged batch (no formulas or macros are evaluated)")
async def import_content(import_id: UUID, request: Request, actor: ActorContext = Depends(require_actor), service: Any = Depends(runtime)) -> dict[str, Any]:
    media_type = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    if media_type not in ("text/csv", "application/csv", "text/plain"):
        raise PartsIQError("UNSUPPORTED_MEDIA_TYPE", detail="Upload the import as text/csv.")
    return await service.upload_import_content(actor, import_id, await request.body())


@router.get("/admin/imports/{import_id}/preview", summary="Dry-run report: row issues and the changes a publish would make")
async def import_preview(import_id: UUID, actor: ActorContext = Depends(require_actor), service: Any = Depends(runtime)) -> dict[str, Any]:
    return await service.import_preview(actor, import_id)


@router.get("/admin/evaluations", summary="Labelled evaluation runs with denominators")
async def evaluations(actor: ActorContext = Depends(require_actor), service: Any = Depends(runtime)) -> list[dict[str, Any]]:
    return await service.list_evaluations(actor)


@router.get("/admin/corrections", summary="Reviewer corrections awaiting curation")
async def corrections(actor: ActorContext = Depends(require_actor), service: Any = Depends(runtime)) -> list[dict[str, Any]]:
    return await service.list_corrections(actor)


@router.post("/admin/corrections/{correction_id}/reviewed", summary="Mark a correction reviewed (it is still not ground truth until curated)")
async def correction_reviewed(correction_id: UUID, actor: ActorContext = Depends(require_actor), service: Any = Depends(runtime), _key: UUID = Depends(idempotency_key)) -> dict[str, Any]:
    return await service.mark_correction_reviewed(actor, correction_id)
