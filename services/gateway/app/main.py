"""Gateway application entry point."""

import httpx
from fastapi import FastAPI

from partsiq_common.app_factory import create_service_app

from app import __version__
from app.config import GatewaySettings
from app.rate_limit import FixedWindowRateLimiter
from app.routes import router
from app.security import parse_api_keys

settings = GatewaySettings()


async def on_startup(app: FastAPI) -> None:
    app.state.api_keys = parse_api_keys(settings.api_keys.get_secret_value())
    app.state.rate_limiter = FixedWindowRateLimiter(
        app.state.resources.redis,
        limit=settings.rate_limit_per_minute,
        window_seconds=60,
    )
    app.state.upstreams = {
        "orchestrator": str(settings.orchestrator_url).rstrip("/"),
        "search": str(settings.search_url).rstrip("/"),
    }
    app.state.http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(settings.upstream_timeout_seconds, connect=settings.upstream_connect_timeout_seconds),
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        follow_redirects=False,
    )


async def on_shutdown(app: FastAPI) -> None:
    client: httpx.AsyncClient | None = getattr(app.state, "http_client", None)
    if client is not None:
        await client.aclose()


app = create_service_app(
    settings,
    title="PartsIQ Gateway",
    version=__version__,
    routers=[router],
    requires_redis=True,
    on_startup=on_startup,
    on_shutdown=on_shutdown,
)
