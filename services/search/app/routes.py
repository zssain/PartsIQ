"""HTTP routes for the search service."""

from fastapi import APIRouter, Path, Request

from app import schemas
from app.service import SearchService

router = APIRouter(prefix="/v1/search", tags=["search"])


def _service(request: Request) -> SearchService:
    return request.app.state.search_service


@router.post("/identify", response_model=schemas.IdentifyResponse)
async def identify(body: schemas.IdentifyRequest, request: Request) -> schemas.IdentifyResponse:
    """Identify the machine configuration from a description and/or serial number."""
    return await _service(request).identify(body)


@router.post("/parts", response_model=schemas.PartSearchResponse)
async def search_parts(body: schemas.PartSearchRequest, request: Request) -> schemas.PartSearchResponse:
    """Rank parts compatible with a configuration against a free-text or part-number query."""
    return await _service(request).search_parts(body)


@router.get("/parts/{part_number}", response_model=schemas.PartDetailResponse)
async def part_detail(
    request: Request, part_number: str = Path(min_length=3, max_length=64)
) -> schemas.PartDetailResponse:
    """Look up a part number, following supersessions to the current part."""
    return await _service(request).part_detail(part_number)


@router.post("/fulfilment", response_model=schemas.FulfilmentResponse)
async def fulfilment(body: schemas.FulfilmentRequest, request: Request) -> schemas.FulfilmentResponse:
    """Recommend which warehouses should supply a quantity of a part to a destination."""
    return await _service(request).plan_fulfilment(body)


@router.get("/warehouses", response_model=list[schemas.WarehouseOut])
async def warehouses(request: Request) -> list[schemas.WarehouseOut]:
    return await _service(request).list_warehouses()
