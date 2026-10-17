"""Stage timing, payload redaction and optional Langfuse tracing.

Guarantees (F64, F67):
  * Timing uses a monotonic clock so it is immune to wall-clock adjustment.
  * Redaction strips secrets and never logs a raw key or a full photo.
  * Tracing is optional: when disabled OR when the exporter errors, the system keeps
    working. Budget accounting (ai/budget.py) stays local and authoritative regardless.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import TracebackType
from typing import Any

logger = logging.getLogger("partsiq.telemetry")

# Substrings that mark a value as sensitive; such values are never emitted.
_SECRET_HINTS = ("key", "secret", "token", "password", "authorization", "jwt", "credential")
# Fields whose contents are large/binary and must be reduced to a size marker.
_BINARY_FIELDS = ("image_base64", "image", "photo", "bytes")
_MAX_VALUE_LEN = 256

Primitive = str | int | bool | None


def redact_payload(payload: Mapping[str, Any]) -> dict[str, Primitive]:
    """Return a bounded, secret-free copy safe for logs, traces and the audit table."""
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
        if isinstance(value, (int, bool)) or value is None:
            safe[key] = value
        else:
            text = str(value)
            safe[key] = text if len(text) <= _MAX_VALUE_LEN else text[:_MAX_VALUE_LEN] + "…"
    return safe


@dataclass
class Stage:
    """Context manager measuring one pipeline stage with a monotonic clock."""

    name: str
    duration_ms: float = 0.0
    status: str = "ok"
    _start: float = field(default=0.0, init=False, repr=False)

    def __enter__(self) -> "Stage":
        self._start = time.monotonic()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        self.duration_ms = round((time.monotonic() - self._start) * 1000, 3)
        self.status = "ok" if exc_type is None else "error"
        return False  # never suppress exceptions


@dataclass
class Tracer:
    """Optional trace emitter. A disabled tracer or an exporter outage is a no-op."""

    enabled: bool = False
    _exporter: Any = None

    def emit(self, event: str, fields: Mapping[str, Any], **ids: str | None) -> None:
        """Emit a redacted trace event. Never raises: tracing must not break a request."""
        if not self.enabled or self._exporter is None:
            return
        safe = redact_payload(dict(fields))
        safe.update({k: v for k, v in ids.items() if v is not None})
        try:
            self._exporter.event(name=event, **safe)
        except Exception:  # exporter outage must never break approval (F67)
            logger.warning("trace export failed; continuing", extra={"event": event}, exc_info=True)


@dataclass
class LangfuseExporter:
    """Optional Langfuse-backed exporter (prompt 23, F67).

    Lazily imports langfuse so the library is NOT required unless tracing is wired; payloads
    are already redacted by the Tracer before they arrive here, and every export is bounded by
    a strict timeout. Any error is left to propagate to the Tracer, which swallows it — a
    tracing outage never breaks a request and never bypasses local budget accounting.
    """

    public_key: str
    secret_key: str
    host: str
    timeout_seconds: float = 2.0
    _client: Any = field(default=None, init=False, repr=False)

    def _ensure(self) -> Any:
        if self._client is None:
            from langfuse import Langfuse  # imported lazily; optional dependency

            self._client = Langfuse(
                public_key=self.public_key, secret_key=self.secret_key, host=self.host,
                timeout=self.timeout_seconds,
            )
        return self._client

    def event(self, *, name: str, **fields: Primitive) -> None:
        self._ensure().create_event(name=name, metadata=dict(fields))


def build_tracer(*, enabled: bool, exporter: Any = None) -> Tracer:
    """Construct a Tracer. Disabled or exporter-less -> a safe no-op."""
    return Tracer(enabled=enabled and exporter is not None, _exporter=exporter)
