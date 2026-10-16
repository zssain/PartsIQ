"""Factory that builds a FastAPI application with shared infrastructure wired in."""

import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass

import asyncpg
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from partsiq_common.config import BaseServiceSettings
from partsiq_common.db import create_db_pool
from partsiq_common.health import router as health_router
from partsiq_common.logging import configure_logging
from partsiq_common.middleware import RequestContextMiddleware

logger = logging.getLogger("partsiq.app")

LifecycleHook = Callable[[FastAPI], Awaitable[None]]


@dataclass(slots=True)
class ServiceResources:
    """External connections owned by a service for its whole lifetime."""

    db_pool: asyncpg.Pool | None
    redis: Redis | None


def create_service_app(
    settings: BaseServiceSettings,
    *,
    title: str,
    version: str,
    routers: Sequence[APIRouter] = (),
    requires_database: bool = False,
    requires_redis: bool = False,
    on_startup: LifecycleHook | None = None,
    on_shutdown: LifecycleHook | None = None,
) -> FastAPI:
    """Create a service application with logging, health checks and managed connections."""
    configure_logging(settings.service_name, settings.log_level)

    if requires_redis and settings.redis_url is None:
        raise RuntimeError("REDIS_URL must be configured for a service that requires Redis")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        db_pool = await create_db_pool(settings) if requires_database else None
        redis = Redis.from_url(str(settings.redis_url), decode_responses=True) if requires_redis else None
        app.state.settings = settings
        app.state.resources = ServiceResources(db_pool=db_pool, redis=redis)
        try:
            if on_startup is not None:
                await on_startup(app)
            logger.info("service started", extra={"version": version, "environment": settings.environment})
            yield
        finally:
            if on_shutdown is not None:
                await on_shutdown(app)
            if redis is not None:
                await redis.aclose()
            if db_pool is not None:
                await db_pool.close()
            logger.info("service stopped")

    is_production = settings.environment == "production"
    app = FastAPI(
        title=title,
        version=version,
        lifespan=lifespan,
        docs_url=None if is_production else "/docs",
        redoc_url=None,
        openapi_url=None if is_production else "/openapi.json",
    )
    app.add_middleware(RequestContextMiddleware)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled exception", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "message": "An unexpected error occurred.",
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    app.include_router(health_router)
    for router in routers:
        app.include_router(router)
    return app
