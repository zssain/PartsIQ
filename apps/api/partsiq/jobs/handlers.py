"""Job-kind handler registry and bounded concurrency (prompt 15 — F51, F52).

Ported and consolidated from ``services/worker/app/dispatcher.py``. The worker runs inside
the SAME ``partsiq`` package, so the dispatcher does not import every job module itself:
each owning prompt registers its handler here (prompt 16 registers ``nameplate``, prompt 17
``export_pdf``, …). The registry maps a job ``kind`` to the coroutine that runs it, and the
:class:`ConcurrencyGuard` bounds how many heavy jobs of a kind run at once so background OCR
and PDF rendering never starve HTTP intake (F51).

Dispatch is allowlisted: only a kind whose handler is registered will run. The eight valid
kinds are the ``JobLease.kind`` literals — nameplate, export_pdf, catalog_import,
catalog_publish, storage_cleanup, workflow, analytics_sync, catalog_sync.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

# The complete set of dispatchable job kinds (mirrors JobLease.kind). A handler may only be
# registered for one of these; any other kind is rejected so a typo cannot create a silent
# no-op job. Handlers for each are registered by their owning prompt at worker startup.
JOB_KINDS: frozenset[str] = frozenset(
    {
        "nameplate",
        "export_pdf",
        "catalog_import",
        "catalog_publish",
        "storage_cleanup",
        "workflow",
        "analytics_sync",
        "catalog_sync",
    }
)

# Initial bounded concurrency per job kind: one OCR and one PDF at a time so heavy work never
# starves HTTP intake (F51). Kinds absent here fall back to DEFAULT_LIMIT (1).
CONCURRENCY_LIMITS: dict[str, int] = {"nameplate": 1, "export_pdf": 1}
DEFAULT_LIMIT = 1

JobHandler = Callable[..., Awaitable[Any]]
_HANDLERS: dict[str, JobHandler] = {}


def register_handler(kind: str, handler: JobHandler) -> None:
    """Register the coroutine that runs jobs of ``kind``; raises for an unknown kind."""
    if kind not in JOB_KINDS:
        raise ValueError(f"unknown job kind: {kind!r}")
    _HANDLERS[kind] = handler


def get_handler(kind: str) -> JobHandler | None:
    """Return the registered handler for ``kind``, or ``None`` if none is registered."""
    return _HANDLERS.get(kind)


def registered_kinds() -> frozenset[str]:
    """The kinds that currently have a handler (the active dispatch allowlist)."""
    return frozenset(_HANDLERS)


def clear_handlers() -> None:
    """Drop every registered handler (test isolation / worker teardown only)."""
    _HANDLERS.clear()


class ConcurrencyGuard:
    """Tracks in-flight jobs per kind and enforces the per-kind concurrency bound.

    ``acquire`` admits a job only while the kind is under its limit; ``release`` frees a slot.
    The guard is a single-worker in-process counter — durability lives in the job rows, not
    here — so a restart simply starts with every slot free.
    """

    def __init__(self, limits: dict[str, int] | None = None) -> None:
        self._limits = dict(limits if limits is not None else CONCURRENCY_LIMITS)
        self._running: dict[str, int] = {}

    def limit_for(self, kind: str) -> int:
        return self._limits.get(kind, DEFAULT_LIMIT)

    def can_run(self, kind: str) -> bool:
        return self._running.get(kind, 0) < self.limit_for(kind)

    def acquire(self, kind: str) -> bool:
        if not self.can_run(kind):
            return False
        self._running[kind] = self._running.get(kind, 0) + 1
        return True

    def release(self, kind: str) -> None:
        self._running[kind] = max(0, self._running.get(kind, 0) - 1)
