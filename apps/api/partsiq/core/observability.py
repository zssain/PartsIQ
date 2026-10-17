"""Structured logs, monotonic stage timing and optional Langfuse tracing (foundation 23).

Ports ``libs/partsiq_common/partsiq_common/telemetry.py`` onto the single ``partsiq``
package. The guarantees characterized by the legacy F64/F67 acceptance tests are preserved
exactly:

  * Timing uses a MONOTONIC clock (:class:`Stage`) so a wall-clock adjustment can never make
    a duration negative or zero out an elapsed interval. UTC timestamps describe *when* a
    stage began; the monotonic clock measures *how long* it took.
  * Redaction (:func:`redact_payload`) strips secrets — anything whose key looks like a key,
    secret, token, password, authorization header, JWT, credential or a signed URL — and
    reduces binary/image fields to a size marker. A raw key, a full photo, a JWT, a signed
    URL or a database error string is NEVER emitted to a log or a trace (CONSTRAINTS 17).
  * Tracing is OPTIONAL and OUTAGE-SAFE. A disabled tracer or a failing exporter is a no-op:
    :meth:`Tracer.emit` never raises, so an exporter outage can never break approval or any
    business transaction (F67). Budget accounting (:mod:`partsiq.ai.budget`) stays local and
    authoritative regardless of whether a trace was emitted.
  * The Langfuse exporter imports ``langfuse`` LAZILY (optional ``[trace]`` extra) and bounds
    every export with a strict timeout. The app runs with ``langfuse`` absent.

This module performs no provider or database side effects at import time.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import TracebackType
from typing import Any, Literal
from uuid import UUID

from partsiq.core.api_models import TraceStage, TraceView

logger = logging.getLogger("partsiq.observability")

# Substrings that mark a KEY as sensitive; the value is replaced with "[redacted]".
# Covers secrets, JWTs and signed URLs (CONSTRAINTS 17): no raw key/JWT/signed URL in logs.
_SECRET_HINTS = (
    "key",
    "secret",
    "token",
    "password",
    "authorization",
    "jwt",
    "credential",
    "signed_url",
    "signature",
    "cookie",
    "bearer",
)
# Fields whose contents are large/binary and must be reduced to a size marker, never logged.
_BINARY_FIELDS = ("image_base64", "image", "photo", "bytes", "attachment")
# Substrings in a VALUE that mark it as a URL carrying a signature/credential query string.
_SIGNED_URL_MARKERS = ("x-amz-signature", "signature=", "token=", "sig=", "se=&sig")
_MAX_VALUE_LEN = 256

Primitive = str | int | bool | None


def _looks_like_signed_url(text: str) -> bool:
    lowered = text.lower()
    if not (lowered.startswith("http://") or lowered.startswith("https://")):
        return False
    return any(marker in lowered for marker in _SIGNED_URL_MARKERS)


def redact_payload(payload: Mapping[str, Any]) -> dict[str, Primitive]:
    """Return a bounded, secret-free copy of ``payload`` safe for logs, traces and audit.

    A value is dropped to ``"[redacted]"`` when its key names a secret/JWT/signed URL, or when
    its value itself looks like a signed/credentialed URL. Binary/image fields collapse to a
    ``<bytes:N>`` marker so a full photo is never serialized. Every surviving scalar is capped
    at :data:`_MAX_VALUE_LEN` so an oversized value cannot bloat a log line. The returned dict
    contains only JSON-safe primitives.
    """
    safe: dict[str, Primitive] = {}
    for key, value in payload.items():
        lowered = key.lower()
        if any(hint in lowered for hint in _SECRET_HINTS):
            safe[key] = "[redacted]"
            continue
        if any(field_name in lowered for field_name in _BINARY_FIELDS) and value is not None:
            length = len(value) if hasattr(value, "__len__") else 0
            safe[key] = f"<bytes:{length}>"
            continue
        if isinstance(value, bool) or isinstance(value, int) or value is None:
            safe[key] = value
            continue
        text = str(value)
        if _looks_like_signed_url(text):
            safe[key] = "[redacted-url]"
            continue
        safe[key] = text if len(text) <= _MAX_VALUE_LEN else text[:_MAX_VALUE_LEN] + "…"
    return safe


def log_event(level: int, message: str, **fields: Any) -> None:
    """Emit one structured log record with a REDACTED ``extra`` payload.

    A convenience wrapper so call sites cannot accidentally log a secret: every field is run
    through :func:`redact_payload` before it reaches the logging subsystem. Never raises.
    """
    try:
        logger.log(level, message, extra={"fields": redact_payload(fields)})
    except Exception:  # logging must never break a business path
        logger.warning("structured log emission failed; continuing", exc_info=True)


@dataclass
class Stage:
    """Context manager measuring one pipeline stage with a monotonic clock.

    ``started_at`` is a UTC wall-clock timestamp for display/ordering; ``duration_ms`` is
    computed from :func:`time.monotonic` so it is immune to clock adjustment. On exit the
    status becomes ``"ok"`` when no exception propagated, ``"error"`` otherwise; the exception
    is never suppressed. ``error_code`` is set when the propagating exception exposes a stable
    ``code`` attribute (e.g. :class:`~partsiq.core.errors.PartsIQError`).
    """

    name: str
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    duration_ms: float = 0.0
    status: str = "ok"
    error_code: str | None = None
    _start: float = field(default=0.0, init=False, repr=False)

    def __enter__(self) -> "Stage":
        self._start = time.monotonic()
        self.started_at = datetime.now(UTC)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> Literal[False]:
        self.duration_ms = round((time.monotonic() - self._start) * 1000, 3)
        if exc_type is None:
            self.status = "ok"
        else:
            self.status = "error"
            code = getattr(exc, "code", None)
            self.error_code = str(code) if code is not None else None
        return False  # never suppress exceptions

    def as_trace_stage(self) -> TraceStage:
        """Convert this measured stage into the typed :class:`TraceStage` contract."""
        return TraceStage(
            stage=self.name,
            started_at=self.started_at,
            duration_ms=self.duration_ms,
            status=self.status,
            error_code=self.error_code,
        )


def build_trace_view(enquiry_id: UUID, revision: int, stages: list[Stage]) -> TraceView:
    """Assemble a :class:`TraceView` from measured stages for one enquiry/revision (F67)."""
    return TraceView(
        enquiry_id=enquiry_id,
        revision=revision,
        stages=[stage.as_trace_stage() for stage in stages],
    )


@dataclass
class Tracer:
    """Optional trace emitter. A disabled tracer or an exporter outage is a no-op.

    The exporter is anything exposing ``event(name=..., **fields)``. Payloads are redacted
    here before they ever reach the exporter, and identifiers (request/enquiry/job ids) are
    attached as extra fields so a trace can be correlated without carrying any secret.
    """

    enabled: bool = False
    _exporter: Any = None

    def emit(self, event: str, fields: Mapping[str, Any], **ids: str | None) -> None:
        """Emit a REDACTED trace event. Never raises: tracing must not break a request (F67)."""
        if not self.enabled or self._exporter is None:
            return
        safe = redact_payload(dict(fields))
        safe.update({k: v for k, v in ids.items() if v is not None})
        try:
            self._exporter.event(name=event, **safe)
        except Exception:  # exporter outage must never break approval (F67)
            logger.warning(
                "trace export failed; continuing", extra={"event": event}, exc_info=True
            )

    def emit_stage(self, event: str, stage: Stage, **ids: str | None) -> None:
        """Emit a measured :class:`Stage` as a redacted trace span (status + duration only)."""
        self.emit(
            event,
            {
                "stage": stage.name,
                "status": stage.status,
                "duration_ms": stage.duration_ms,
                "error_code": stage.error_code,
            },
            **ids,
        )


@dataclass
class LangfuseExporter:
    """Optional Langfuse-backed exporter (foundation 23, F67).

    ``langfuse`` is imported LAZILY the first time an event is exported, so the library is NOT
    required unless tracing is actually wired (it is the common ``[trace]`` extra). Payloads
    are already redacted by the :class:`Tracer` before they arrive here, and every export is
    bounded by a strict ``timeout_seconds``. Any error propagates to the Tracer, which swallows
    it — a tracing outage never breaks a request and never bypasses local budget accounting.
    """

    public_key: str
    secret_key: str
    host: str
    timeout_seconds: float = 2.0
    _client: Any = field(default=None, init=False, repr=False)

    def _ensure(self) -> Any:
        if self._client is None:
            from langfuse import Langfuse  # type: ignore[import-not-found]  # noqa: PLC0415 - lazy optional import

            self._client = Langfuse(
                public_key=self.public_key,
                secret_key=self.secret_key,
                host=self.host,
                timeout=self.timeout_seconds,
            )
        return self._client

    def event(self, *, name: str, **fields: Primitive) -> None:
        self._ensure().create_event(name=name, metadata=dict(fields))


def build_tracer(*, enabled: bool, exporter: Any = None) -> Tracer:
    """Construct a :class:`Tracer`. Disabled or exporter-less yields a safe no-op."""
    return Tracer(enabled=enabled and exporter is not None, _exporter=exporter)
