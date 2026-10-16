"""Structured JSON logging with request-ID correlation across services."""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

_request_id_var: ContextVar[str | None] = ContextVar("partsiq_request_id", default=None)

_RESERVED_RECORD_ATTRIBUTES = frozenset(
    logging.LogRecord("", 0, "", 0, "", None, None).__dict__.keys() | {"message", "asctime"}
)


def get_request_id() -> str | None:
    """Return the request ID bound to the current execution context, if any."""
    return _request_id_var.get()


def bind_request_id(request_id: str) -> object:
    """Bind a request ID to the current context and return a token for later reset."""
    return _request_id_var.set(request_id)


def reset_request_id(token: object) -> None:
    """Restore the request ID context to its state before the matching bind call."""
    _request_id_var.reset(token)  # type: ignore[arg-type]


class JsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects suitable for log aggregation."""

    def __init__(self, service_name: str) -> None:
        super().__init__()
        self._service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self._service_name,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = get_request_id()
        if request_id is not None:
            payload["request_id"] = request_id
        for key, value in record.__dict__.items():
            if key not in _RESERVED_RECORD_ATTRIBUTES and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(service_name: str, level: str) -> None:
    """Route all application and server logs through a single JSON handler on stdout."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service_name))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    for name in ("uvicorn", "uvicorn.error"):
        server_logger = logging.getLogger(name)
        server_logger.handlers.clear()
        server_logger.propagate = True

    # Access logging is emitted by RequestContextMiddleware with richer fields.
    logging.getLogger("uvicorn.access").disabled = True
