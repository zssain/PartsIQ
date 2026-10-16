"""Worker internal signing route (prompt 15).

The worker holds the Storage-admin credential (prompt 04) and exposes exactly ONE
authenticated internal route — signing a download for a typed, already-authorized resource.
It is reachable only on the Docker network behind an internal service token (CONSTRAINTS
rule 13); it is never a public route and never a database-REST surface. The worker makes no
outbound call to the orchestrator (ARCHITECTURE section 4): it only writes workflow events.
"""
from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, Header, Request

from app.storage import sign_download
from partsiq_common.contracts import DownloadRequest, DownloadTicket
from partsiq_common.errors import PartsIQError

router = APIRouter(prefix="/internal", tags=["internal"])

_TOKEN_ENV = "INTERNAL_SERVICE_TOKEN"


def verify_internal_token(provided: str | None) -> None:
    """Constant-time check of the internal service token; unconfigured means local dev."""
    expected = os.environ.get(_TOKEN_ENV)
    if not expected:
        return  # local dev / tests: no token configured
    if not provided or not hmac.compare_digest(provided, expected):
        raise PartsIQError("UNAUTHENTICATED", internal_detail="missing or invalid internal service token")


@router.post("/storage/sign-download", response_model=None)
async def sign_download_route(
    request: Request,
    body: DownloadRequest,
    x_internal_token: str | None = Header(default=None),
) -> DownloadTicket:
    verify_internal_token(x_internal_token)
    backend = request.app.state.storage_backend
    resolve_key = request.app.state.resolve_key
    url = await sign_download(body, backend=backend, resolve_key=resolve_key)
    from datetime import UTC, datetime, timedelta

    from app.storage import SIGNED_URL_TTL_SECONDS

    expires = datetime.now(UTC) + timedelta(seconds=SIGNED_URL_TTL_SECONDS)
    return DownloadTicket(url=url, expires_at=expires)
