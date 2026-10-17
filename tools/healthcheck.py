"""In-image container liveness probe (prompt 24 — single-workflow edition).

Used by the single `partsiq` application image's HEALTHCHECK. It makes ONE local HTTP GET to
the API's ``/health`` route (``partsiq.main:create_app`` exposes it) and exits 0 only on a
200 response. It spends NO provider credits and talks to nothing but the local process, so
it is safe in fixture mode and before any live allowance is confirmed.

Usage: ``python /app/tools/healthcheck.py`` (exit 0 = live, non-zero = not live). The host
and port are overridable via ``HEALTHCHECK_URL`` for the worker role, which has no HTTP port
and therefore uses a trivial ``--process`` style check in compose instead of this script.
"""
from __future__ import annotations

import os
import sys
import urllib.request

_DEFAULT_URL = "http://127.0.0.1:8000/health"
_TIMEOUT_SECONDS = 3


def probe(url: str = _DEFAULT_URL, *, timeout: int = _TIMEOUT_SECONDS) -> int:
    """Return 0 when ``url`` answers HTTP 200, otherwise 1. Never raises."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 (local only)
            return 0 if response.status == 200 else 1
    except Exception:  # any connect/timeout/HTTP error means "not live"
        return 1


def main() -> int:
    url = os.environ.get("HEALTHCHECK_URL", _DEFAULT_URL)
    return probe(url)


if __name__ == "__main__":
    sys.exit(main())
