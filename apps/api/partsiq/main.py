"""FastAPI application assembly (foundation 01).

``create_app`` builds the single public API: a lifespan that assembles the dependency
container (and opens database pools only when a runtime DSN is configured), request-id
middleware, RFC9457 Problem error handling, CORS restricted to the configured origins,
and the ``/v1`` router. Liveness/readiness never spend Snowflake or OpenAI credits.
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .api.router import include_completed_features, v1_router
from .core.db import Database
from .core.dependencies import build_container, build_fixture_verifier
from .core.errors import PartsIQError, build_problem
from .core.settings import Settings, load_settings

logger = logging.getLogger("partsiq")

REQUEST_ID_HEADER = "X-Request-Id"
PROBLEM_MEDIA_TYPE = "application/problem+json"


def _request_id(request: Request) -> UUID:
    rid = getattr(request.state, "request_id", None)
    return rid if isinstance(rid, UUID) else uuid4()


def _problem_response(code: str, request: Request, detail: str | None = None) -> JSONResponse:
    problem = build_problem(code, _request_id(request), detail)
    return JSONResponse(
        status_code=problem.status,
        content=problem.model_dump(mode="json"),
        media_type=PROBLEM_MEDIA_TYPE,
        headers={REQUEST_ID_HEADER: str(problem.request_id)},
    )


@asynccontextmanager
async def _lifespan(app: FastAPI):
    settings: Settings = getattr(app.state, "settings_override", None) or load_settings()
    # Assemble the injected adapters. In fixture mode this wires the fixture catalogue, the
    # in-memory demo store and the in-memory enquiry/workflow journey so the app serves REAL
    # seed-42 responses with no database.
    container = build_container(settings)
    # Open pools only when a runtime DSN is configured; fixture/offline mode has none.
    if settings.database_url_api:
        container.database = await Database.connect(settings, roles=("api",))
    app.state.container = container
    app.state.settings = settings
    # Wire the actor verifier so ``require_actor`` can resolve a trusted actor. Fixture mode
    # resolves an anonymous demo actor from an ``X-Demo-Token`` header; DB mode wires the real
    # Supabase JWT verifier (owner work; left unset here so protected routes refuse cleanly).
    if settings.data_source == "fixture" and getattr(app.state, "actor_verifier", None) is None:
        app.state.actor_verifier = build_fixture_verifier()
    try:
        yield
    finally:
        if container.database is not None:
            await container.database.close()


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(
        title="PartsIQ",
        version="0.1.0",
        description="Bilingual spare-parts enquiry and human-review application.",
        lifespan=_lifespan,
    )
    if settings is not None:
        app.state.settings_override = settings

    origins = (settings or load_settings()).allowed_origin_list
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", REQUEST_ID_HEADER],
    )

    @app.middleware("http")
    async def request_id_middleware(
        request: Request, call_next: Callable[[Request], Awaitable]
    ):
        incoming = request.headers.get(REQUEST_ID_HEADER)
        try:
            request.state.request_id = UUID(incoming) if incoming else uuid4()
        except ValueError:
            request.state.request_id = uuid4()
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = str(request.state.request_id)
        return response

    @app.exception_handler(PartsIQError)
    async def _handle_partsiq_error(request: Request, exc: PartsIQError) -> JSONResponse:
        if exc.internal_detail:
            logger.warning("partsiq_error code=%s detail=%s", exc.code, exc.internal_detail)
        return _problem_response(exc.code, request, exc.detail)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _problem_response("VALIDATION_FAILED", request, "One or more fields are invalid.")

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {
            400: "MALFORMED_REQUEST",
            401: "UNAUTHENTICATED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            413: "PAYLOAD_TOO_LARGE",
            415: "UNSUPPORTED_MEDIA_TYPE",
            429: "QUOTA_EXCEEDED",
        }.get(exc.status_code, "DEPENDENCY_UNAVAILABLE")
        return _problem_response(code, request)

    @app.get("/health", tags=["meta"], summary="Liveness (no provider credits spent)")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/livez", tags=["meta"], summary="Liveness probe")
    async def livez() -> dict[str, str]:
        return {"status": "live"}

    # Import and mount every completed feature router additively onto ``/v1`` (idempotent).
    include_completed_features()
    app.include_router(v1_router)
    return app
