"""HTTP routes for the search service.

Every route requires the internal service token (CONSTRAINTS.md rule 13): the search
service is private and never faces the public internet. When a token is configured it is
enforced with a constant-time comparison; an unconfigured token is treated as local-dev
and allowed (production always configures INTERNAL_SERVICE_TOKEN).

The module-level ``router`` is a prefix-free parent that mounts the public-to-the-mesh
``/v1/search`` routes and the ``/internal`` routes (F35 stock freshness), so main.py keeps
including a single router.
"""

import hmac
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Request, status

from app import schemas
from app.features.f35_stock_freshness import F35Request, F35Result, check_stock_freshness
from app.service import SearchService
from partsiq_common.errors import PartsIQError


async def require_internal_token(
    request: Request, x_internal_token: str | None = Header(default=None)
) -> None:
    settings = getattr(request.app.state, "settings", None)
    expected = getattr(settings, "internal_service_token", None) if settings else None
    if not expected:
        return  # no token configured: local development only
    if x_internal_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="internal token required")
    if not hmac.compare_digest(x_internal_token, expected):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid internal token")


router = APIRouter()  # prefix-free parent imported by main.py
search_router = APIRouter(prefix="/v1/search", tags=["search"], dependencies=[Depends(require_internal_token)])
internal_router = APIRouter(prefix="/internal", tags=["internal"], dependencies=[Depends(require_internal_token)])


def _service(request: Request) -> SearchService:
    return request.app.state.search_service


@search_router.get("/readiness")
async def readiness(request: Request) -> dict[str, bool]:
    """Lexical readiness and semantic capability reported separately."""
    return _service(request).readiness()


@search_router.post("/identify", response_model=schemas.IdentifyResponse)
async def identify(body: schemas.IdentifyRequest, request: Request) -> schemas.IdentifyResponse:
    """Identify the machine configuration from a description and/or serial number."""
    return await _service(request).identify(body)


@search_router.post("/parts", response_model=schemas.PartSearchResponse)
async def search_parts(body: schemas.PartSearchRequest, request: Request) -> schemas.PartSearchResponse:
    """Rank parts compatible with a configuration against a free-text or part-number query."""
    return await _service(request).search_parts(body)


@search_router.get("/parts/{part_number}", response_model=schemas.PartDetailResponse)
async def part_detail(
    request: Request, part_number: str = Path(min_length=3, max_length=64)
) -> schemas.PartDetailResponse:
    """Look up a part number, following supersessions to the current part."""
    return await _service(request).part_detail(part_number)


@search_router.post("/fulfilment", response_model=schemas.FulfilmentResponse)
async def fulfilment(body: schemas.FulfilmentRequest, request: Request) -> schemas.FulfilmentResponse:
    """Recommend which warehouses should supply a quantity of a part to a destination."""
    return await _service(request).plan_fulfilment(body)


@search_router.get("/warehouses", response_model=list[schemas.WarehouseOut])
async def warehouses(request: Request) -> list[schemas.WarehouseOut]:
    return await _service(request).list_warehouses()


@internal_router.post("/stock/check", response_model=None)
async def stock_check(body: F35Request, request: Request) -> F35Result:
    """F35: re-check stock freshness for a plan's facts. The stock reader is injected (BLOCKED here)."""
    reader = getattr(request.app.state, "stock_reader", None)
    if reader is None:
        raise HTTPException(status_code=503, detail="stock reader unavailable")
    # The caller (orchestrator, during the locked approval re-read) propagates its actor; the
    # freshness check itself is not role-gated, so a system actor context is sufficient here.
    actor = getattr(request.app.state, "system_actor", None)
    try:
        return await check_stock_freshness(actor, body, reader=reader, now=datetime.now(UTC))
    except PartsIQError as exc:
        raise HTTPException(status_code=exc.http_status, detail=exc.message) from exc


router.include_router(search_router)
router.include_router(internal_router)
