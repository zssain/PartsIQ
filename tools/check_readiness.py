"""Readiness report (prompt 23 — F64/F67 operability).

Contract: ``async def readiness_report() -> ReadinessReport``.

Probes each dependency independently and reports a boolean per subsystem. A probe that
cannot connect (or is not configured) reports False — missing access is BLOCKED, not passed.
Lexical and semantic search readiness are reported SEPARATELY (prompt 06). Probes are
injected so the report is testable offline; the default report is all-False (nothing wired).
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from partsiq_common.contracts import ReadinessReport

Probe = Callable[[], Awaitable[bool]]

_SUBSYSTEMS = ("database", "redis", "search_lexical", "search_semantic", "ai_credit_enabled", "storage")


async def _false() -> bool:
    return False


async def _run(probe: Probe) -> bool:
    try:
        return bool(await probe())
    except Exception:  # a failing/unreachable probe is not-ready, never an error that passes
        return False


async def readiness_report(*, probes: dict[str, Probe] | None = None) -> ReadinessReport:
    probes = probes or {}
    results = {name: await _run(probes.get(name, _false)) for name in _SUBSYSTEMS}
    return ReadinessReport(**results)
