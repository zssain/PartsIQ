"""Dependency release-date eligibility gate.

Every direct dependency pin in this kit was captured from the official registry with
a release timestamp (spec/dependency-receipts.json). Nothing released AFTER the
recorded cutoff may be installed without an explicitly recorded exception, so that a
silently-newer build cannot slip in unreviewed (docs/TECH_SPEC.md section 3).

This script reads only the committed receipts; it performs no network access, so it
never claims that a package is installed or that the application is vulnerability free.
It is a documentation-consistency gate, not an application test.
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

# Registry snapshot cutoff recorded in docs/TECH_SPEC.md section 3.
CUTOFF = date(2026, 9, 26)

REPO_ROOT = Path(__file__).resolve().parent.parent
RECEIPTS_PATH = REPO_ROOT / "spec" / "dependency-receipts.json"


def _parse_released(value: str) -> date:
    """Parse an ISO-8601 receipt timestamp (trailing 'Z' allowed) to a date."""
    text = value.strip().replace("Z", "+00:00")
    return datetime.fromisoformat(text).date()


def check_release_eligibility(
    receipts_path: Path = RECEIPTS_PATH, cutoff: date = CUTOFF
) -> list[str]:
    """Return human-readable violation messages; empty list means all eligible."""
    receipts = json.loads(receipts_path.read_text(encoding="utf-8"))
    violations: list[str] = []
    for item in receipts:
        name = item.get("package") or item.get("name") or "<unknown>"
        version = item.get("version", "<unknown>")
        released_raw = item.get("released")
        if not released_raw:
            violations.append(f"{name}=={version}: missing release date in receipt")
            continue
        try:
            released = _parse_released(released_raw)
        except ValueError:
            violations.append(f"{name}=={version}: unparseable release date {released_raw!r}")
            continue
        if released > cutoff:
            violations.append(
                f"{name}=={version}: released {released} is after cutoff {cutoff}; "
                "requires a recorded exception"
            )
        # Cross-check the receipt's own precomputed eligibility flag.
        if item.get("eligible") is False:
            violations.append(f"{name}=={version}: receipt marks eligible=false")
    return violations


def main(argv: list[str] | None = None) -> int:
    violations = check_release_eligibility()
    if violations:
        print(f"Release eligibility FAILED ({len(violations)} issue(s)):")
        for message in violations:
            print(f"  - {message}")
        return 1
    count = len(json.loads(RECEIPTS_PATH.read_text(encoding="utf-8")))
    print(f"Release eligibility passed: {count} receipts, all at or before cutoff {CUTOFF}.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
