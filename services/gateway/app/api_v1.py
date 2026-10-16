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

from fastapi import APIRouter, Header, HTTPException, Path, Request, status
from fastapi.responses import JSONResponse

from app import enquiries as enquiries_uc
from app import uploads as uploads_uc
from app.auth import authenticate
from partsiq_common.contracts import EnquiryCreate, MessageCreate
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
