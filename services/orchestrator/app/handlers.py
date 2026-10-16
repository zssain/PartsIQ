"""Workflow handler registry.

WorkflowHandlers holds the async specialist callables the executable graph nodes call.
Each takes and returns EnquiryState. Blocking states (await_ocr, confirm, clarify,
review) are graph interrupts, NOT handlers. Production startup fails readiness until
every required handler is registered — we never ship runnable fake-success nodes
(prompt 09). Test doubles are injected only by tests.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, fields

from partsiq_common.contracts import EnquiryState

Handler = Callable[[EnquiryState], Awaitable[EnquiryState]]


@dataclass(frozen=True, slots=True)
class WorkflowHandlers:
    intake: Handler
    identify: Handler
    search: Handler
    choose: Handler
    plan: Handler
    draft: Handler
    verify: Handler


REQUIRED_HANDLERS = tuple(f.name for f in fields(WorkflowHandlers))


def missing_handlers(handlers: WorkflowHandlers | None) -> list[str]:
    """Return the names of handlers not yet registered (readiness gate)."""
    if handlers is None:
        return list(REQUIRED_HANDLERS)
    return [name for name in REQUIRED_HANDLERS if getattr(handlers, name, None) is None]


def is_ready(handlers: WorkflowHandlers | None) -> bool:
    return not missing_handlers(handlers)
