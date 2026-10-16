"""Liveness and readiness endpoints for container orchestration."""

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger("partsiq.health")

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    """Report that the process is running. Must not depend on external systems."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(request: Request) -> JSONResponse:
    """Report whether every dependency this service requires is reachable."""
    resources = request.app.state.resources
    timeout = request.app.state.settings.health_check_timeout_seconds
    checks: dict[str, Any] = {}

    if resources.db_pool is not None:
        checks["database"] = await _run_check(_check_database(resources.db_pool), timeout, "database")
    if resources.redis is not None:
        checks["redis"] = await _run_check(resources.redis.ping(), timeout, "redis")

    healthy = all(result == "ok" for result in checks.values())
    return JSONResponse(
        status_code=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "ok" if healthy else "degraded", "checks": checks},
    )


async def _check_database(pool: Any) -> None:
    async with pool.acquire() as connection:
        await connection.fetchval("SELECT 1")


async def _run_check(awaitable: Any, timeout: float, name: str) -> str:
    try:
        await asyncio.wait_for(awaitable, timeout=timeout)
        return "ok"
    except Exception:
        logger.warning("readiness check failed", extra={"dependency": name}, exc_info=True)
        return "unavailable"
