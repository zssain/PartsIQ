"""Search service entry point."""

import asyncio

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from partsiq_common.app_factory import create_service_app
from partsiq_common.embeddings import build_embedding_provider

from app import __version__
from app.config import SearchSettings
from app.repository import SearchRepository
from app.routes import router
from app.service import InvalidRequestError, ResourceNotFoundError, SearchService

settings = SearchSettings()


async def on_startup(app: FastAPI) -> None:
    # Model loading is CPU-bound and slow; keep it off the event loop.
    provider = await asyncio.to_thread(
        build_embedding_provider, settings.embedding_provider, settings.embedding_model_name
    )
    app.state.search_service = SearchService(
        repository=SearchRepository(app.state.resources.db_pool),
        embedding_provider=provider,
        semantic_weight=settings.semantic_weight,
        default_limit=settings.default_result_limit,
    )


app = create_service_app(
    settings,
    title="PartsIQ Search",
    version=__version__,
    routers=[router],
    requires_database=True,
    on_startup=on_startup,
)


def _error(request: Request, status_code: int, error: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": error, "message": message, "request_id": getattr(request.state, "request_id", None)},
    )


@app.exception_handler(ResourceNotFoundError)
async def not_found_handler(request: Request, exc: ResourceNotFoundError) -> JSONResponse:
    return _error(request, 404, "not_found", str(exc))


@app.exception_handler(InvalidRequestError)
async def invalid_request_handler(request: Request, exc: InvalidRequestError) -> JSONResponse:
    return _error(request, 422, "invalid_request", str(exc))
