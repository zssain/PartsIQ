"""Hosted acceptance (prompt 27).

Contract: ``async def run_hosted_acceptance(base_url: str, api_url: str) -> HostedReceipt``.

Runs the four demo scenarios against a HOSTED deployment (each including approval + PDF) and
returns a receipt of what actually passed/failed. Non-HTTPS URLs are rejected outside
localhost. The deployment is NOT claimed available unless every scenario passed — ``is_available``
is the single honest gate. The HTTP client is injected so the control flow is testable offline;
with no client the function refuses rather than fabricating a pass (the hosted checks are
BLOCKED until a real deployment exists).
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from urllib.parse import urlparse

from partsiq_common.contracts import HostedReceipt
from partsiq_common.errors import PartsIQError

SCENARIOS = ("mixed_photo", "missing_serial", "incompatible_number", "local_shortage")
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}

# A scenario checker: given (api_url, scenario) it runs the hosted flow and returns True on
# the expected outcome (incl. approval + PDF). Injected for offline testing.
ScenarioCheck = Callable[[str, str], Awaitable[bool]]


def _https_or_local(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" or (parsed.hostname in _LOCAL_HOSTS)


async def run_hosted_acceptance(
    base_url: str,
    api_url: str,
    *,
    check: ScenarioCheck | None = None,
    now: datetime | None = None,
) -> HostedReceipt:
    for url in (base_url, api_url):
        if not _https_or_local(url):
            raise PartsIQError("MALFORMED_REQUEST", internal_detail=f"non-HTTPS URL rejected: {url}")
    if check is None:
        # No hosted client wired: do not claim availability from nothing (BLOCKED).
        raise PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail="no hosted scenario client configured")

    now = now or datetime.now(UTC)
    passed: list[str] = []
    failed: list[str] = []
    for scenario in SCENARIOS:
        try:
            ok = await check(api_url, scenario)
        except Exception:  # noqa: BLE001 — an errored check is a failed scenario, never a pass
            ok = False
        (passed if ok else failed).append(scenario)

    return HostedReceipt(
        base_url=base_url, api_url=api_url,
        scenarios_passed=passed, scenarios_failed=failed, checked_at=now,
    )


def is_available(receipt: HostedReceipt) -> bool:
    """The deployment is available ONLY when all four scenarios passed and none failed."""
    return not receipt.scenarios_failed and sorted(receipt.scenarios_passed) == sorted(SCENARIOS)
