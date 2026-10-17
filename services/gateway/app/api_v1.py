"""Public v1 API: enquiry intake, messages and attachment confirmation.

Registers the routes that call the intake use cases. Identity comes from the verified
Supabase bearer token; the Idempotency-Key header is required on writes. A durable
commit happens inside the use case, so creation returns 202 only after the enquiry is
persisted (never after an OCR/model call). Business errors map to the public envelope.

Repositories live on app.state and are wired at startup; when unavailable the route
fails closed with 503 rather than guessing.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Path, Query, Request, status
from fastapi.responses import JSONResponse

from app import enquiries as enquiries_uc
from app import ocr_confirmation as ocr_uc
from app import uploads as uploads_uc
from app.auth import authenticate
from app.features import f19_enquiry_history as history_uc
from app.features import f29_evidence_page_viewer as evidence_uc
from app.features import f38_correction_routes as correction_uc
from app.features import f41_internal_notes as notes_uc
from app.features import f42_assignments as assignments_uc
from app.features import f55_saved_machines as machines_uc
from app.features import f56_repeat_enquiry as repeat_uc
from app.features import f57_catalogue_browser as catalogue_uc
from app.features import f58_import_routes as import_uc
from app.features import f59_publish_routes as publish_uc
from app.features import f60_missing_parts_queue as missing_uc
from partsiq_common.contracts import ConfirmExtraction, EnquiryCreate, MessageCreate
from partsiq_common.errors import PartsIQError, error_envelope, http_status_for

router = APIRouter(prefix="/v1", tags=["intake"])


async def _actor(request: Request):
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    return await authenticate(header.split(" ", 1)[1])


def _require(request: Request, name: str):
    value = getattr(request.app.state, name, None)
    if value is None:
        raise HTTPException(status_code=503, detail=f"{name} unavailable")
    return value


def _as_response(error: PartsIQError, request: Request) -> JSONResponse:
    request_id = str(getattr(request.state, "request_id", ""))
    return JSONResponse(
        status_code=http_status_for(error.code),
        content=error_envelope(error.code, request_id, error.message),
    )


@router.get("/enquiries")
async def list_enquiries(
    request: Request,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20),
    status_filter: str | None = Query(default=None, alias="status"),
):
    actor = await _actor(request)
    try:
        result = await history_uc.list_history(
            actor,
            history_uc.F19Request(cursor=cursor, limit=limit, status=status_filter),
            repo=_require(request, "history_repo"),
        )
    except PartsIQError as exc:
        return _as_response(exc, request)
    return result.model_dump(mode="json")


@router.post("/machines")
async def save_machine(body: machines_uc.F55Request, request: Request):
    actor = await _actor(request)
    try:
        result = await machines_uc.save_machine(actor, body, repo=_require(request, "machine_repo"))
    except PartsIQError as exc:
        return _as_response(exc, request)
    return result.model_dump(mode="json")


@router.get("/machines")
async def list_machines(request: Request):
    actor = await _actor(request)
    try:
        results = await machines_uc.list_machines(actor, repo=_require(request, "machine_repo"))
    except PartsIQError as exc:
        return _as_response(exc, request)
    return [r.model_dump(mode="json") for r in results]


@router.patch("/machines/{machine_id}")
async def rename_machine(request: Request, machine_id: UUID = Path(), label: str = Query()):
    actor = await _actor(request)
    try:
        result = await machines_uc.rename_machine(actor, machine_id, label, repo=_require(request, "machine_repo"))
    except PartsIQError as exc:
        return _as_response(exc, request)
    return result.model_dump(mode="json")


@router.delete("/machines/{machine_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_machine(request: Request, machine_id: UUID = Path()):
    actor = await _actor(request)
    try:
        await machines_uc.archive_machine(actor, machine_id, repo=_require(request, "machine_repo"))
    except PartsIQError as exc:
        return _as_response(exc, request)
    return None


@router.post("/enquiries", status_code=status.HTTP_202_ACCEPTED)
async def create_enquiry(body: EnquiryCreate, request: Request, idempotency_key: UUID = Header()):
    actor = await _actor(request)
    try:
        view = await enquiries_uc.create_enquiry(
            actor, body, idempotency_key,
            repo=_require(request, "enquiry_repo"), rate_limiter=_require(request, "rate_allow"),
        )
    except PartsIQError as exc:
        return _as_response(exc, request)
    return view.model_dump(mode="json")


@router.post("/enquiries/{enquiry_id}/messages", status_code=status.HTTP_202_ACCEPTED)
async def add_message(
    body: MessageCreate, request: Request, enquiry_id: UUID = Path(), idempotency_key: UUID = Header()
):
    actor = await _actor(request)
    try:
        view = await enquiries_uc.add_message(
            actor, enquiry_id, body, idempotency_key, repo=_require(request, "enquiry_repo")
        )
    except PartsIQError as exc:
        return _as_response(exc, request)
    return view.model_dump(mode="json")


@router.get("/catalogue/parts")
async def browse_catalogue(
    request: Request,
    query: str | None = Query(default=None),
    model_id: int | None = Query(default=None),
    category: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20),
):
    actor = await _actor(request)
    try:
        result = await catalogue_uc.browse_catalogue(
            actor,
            catalogue_uc.F57Request(query=query, model_id=model_id, category=category, cursor=cursor, limit=limit),
            store=_require(request, "catalogue_read"),
        )
    except PartsIQError as exc:
        return _as_response(exc, request)
    return result.model_dump(mode="json")


@router.get("/catalogue/parts/{part_number}")
async def catalogue_part_detail(request: Request, part_number: str = Path()):
    actor = await _actor(request)
    try:
        detail = await catalogue_uc.part_detail(actor, part_number, store=_require(request, "catalogue_read"))
    except PartsIQError as exc:
        return _as_response(exc, request)
    return detail.model_dump(mode="json")


@router.post("/staff/imports", status_code=status.HTTP_202_ACCEPTED)
async def create_import(body: import_uc.CreateImportBody, request: Request):
    actor = await _actor(request)
    try:
        result = await import_uc.create_import(actor, body, control=_require(request, "import_control"))
    except PartsIQError as exc:
        return _as_response(exc, request)
    return result


@router.get("/staff/imports/{batch_id}")
async def get_import_report(request: Request, batch_id: UUID = Path()):
    actor = await _actor(request)
    try:
        report = await import_uc.get_import_report(actor, batch_id, control=_require(request, "import_control"))
    except PartsIQError as exc:
        return _as_response(exc, request)
    return report


@router.post("/staff/imports/{batch_id}/validate", status_code=status.HTTP_202_ACCEPTED)
async def validate_import(request: Request, batch_id: UUID = Path()):
    actor = await _actor(request)
    try:
        result = await import_uc.request_validate(actor, batch_id, control=_require(request, "import_control"))
    except PartsIQError as exc:
        return _as_response(exc, request)
    return result


@router.post("/staff/enquiries/{enquiry_id}/corrections", status_code=status.HTTP_202_ACCEPTED)
async def correct_enquiry(body: correction_uc.CorrectionBody, request: Request, enquiry_id: UUID = Path()):
    actor = await _actor(request)
    try:
        result = await correction_uc.request_correction(
            actor, enquiry_id, body, forwarder=_require(request, "correction_forwarder")
        )
    except PartsIQError as exc:
        return _as_response(exc, request)
    return result


@router.post("/staff/enquiries/{enquiry_id}/notes", status_code=status.HTTP_201_CREATED)
async def append_note(body: notes_uc.F41Request, request: Request, enquiry_id: UUID = Path()):
    actor = await _actor(request)
    if body.enquiry_id != enquiry_id:
        return _as_response(PartsIQError("MALFORMED_REQUEST", internal_detail="enquiry id mismatch"), request)
    try:
        result = await notes_uc.append_note(actor, body, repo=_require(request, "notes_repo"))
    except PartsIQError as exc:
        return _as_response(exc, request)
    return result.model_dump(mode="json")


@router.get("/staff/enquiries/{enquiry_id}/notes")
async def list_notes(request: Request, enquiry_id: UUID = Path()):
    actor = await _actor(request)
    try:
        notes = await notes_uc.list_notes(actor, enquiry_id, repo=_require(request, "notes_repo"))
    except PartsIQError as exc:
        return _as_response(exc, request)
    return [n.model_dump(mode="json") for n in notes]


@router.post("/staff/enquiries/{enquiry_id}/assignment")
async def assign_enquiry(body: assignments_uc.F42Request, request: Request, enquiry_id: UUID = Path()):
    actor = await _actor(request)
    if body.enquiry_id != enquiry_id:
        return _as_response(PartsIQError("MALFORMED_REQUEST", internal_detail="enquiry id mismatch"), request)
    try:
        result = await assignments_uc.assign_enquiry(actor, body, repo=_require(request, "assignment_repo"))
    except PartsIQError as exc:
        return _as_response(exc, request)
    return result.model_dump(mode="json")


@router.post("/staff/evidence/open")
async def open_evidence(body: evidence_uc.F29Request, request: Request):
    actor = await _actor(request)
    try:
        result = await evidence_uc.open_evidence(actor, body, store=_require(request, "evidence_store"))
    except PartsIQError as exc:
        return _as_response(exc, request)
    return result.model_dump(mode="json")


@router.patch("/staff/missing-parts/{item_id}")
async def update_missing_part(body: missing_uc.MissingPartUpdateBody, request: Request, item_id: UUID = Path()):
    actor = await _actor(request)
    try:
        result = await missing_uc.update_missing_part(
            actor,
            missing_uc.F60Request(
                item_id=item_id, status=body.status, staff_note=body.staff_note,
                expected_revision=body.expected_revision,
            ),
            repo=_require(request, "missing_parts_repo"),
        )
    except PartsIQError as exc:
        return _as_response(exc, request)
    return result.model_dump(mode="json")


@router.post("/staff/catalogue/publish", status_code=status.HTTP_202_ACCEPTED)
async def publish_catalogue(body: publish_uc.PublishBody, request: Request):
    actor = await _actor(request)
    try:
        result = await publish_uc.request_publish(actor, body, queue=_require(request, "publish_queue"))
    except PartsIQError as exc:
        return _as_response(exc, request)
    return result


@router.post("/enquiries/{enquiry_id}/repeat", status_code=status.HTTP_202_ACCEPTED)
async def repeat_enquiry(request: Request, enquiry_id: UUID = Path(), idempotency_key: UUID = Header()):
    actor = await _actor(request)
    try:
        result = await repeat_uc.repeat_enquiry(
            actor,
            repeat_uc.F56Request(source_enquiry_id=enquiry_id, idempotency_key=idempotency_key),
            repo=_require(request, "repeat_repo"),
        )
    except PartsIQError as exc:
        return _as_response(exc, request)
    return result.model_dump(mode="json")


@router.post("/attachments/{attachment_id}/confirm")
async def confirm_upload(request: Request, attachment_id: UUID = Path()):
    actor = await _actor(request)
    try:
        view = await uploads_uc.confirm_upload(
            actor, attachment_id,
            repo=_require(request, "upload_repo"), fetch_bytes=_require(request, "fetch_object_bytes"),
        )
    except PartsIQError as exc:
        return _as_response(exc, request)
    return view.model_dump(mode="json")


@router.post("/enquiries/{enquiry_id}/extractions/{extraction_id}/confirm")
async def confirm_extraction(
    body: ConfirmExtraction, request: Request, enquiry_id: UUID = Path(), extraction_id: UUID = Path()
):
    actor = await _actor(request)
    if body.extraction_id != extraction_id:
        return _as_response(PartsIQError("MALFORMED_REQUEST", internal_detail="extraction id mismatch"), request)
    try:
        view = await ocr_uc.confirm_extraction(actor, enquiry_id, body, repo=_require(request, "ocr_repo"))
    except PartsIQError as exc:
        return _as_response(exc, request)
    return view.model_dump(mode="json")
