"""F68 Recruiter documentation — the guide is complete and makes no invented claims.

Asserts the required sections (overview, architecture, quick start, demo, tests, trade-offs,
limitations), the deterministic-decisions + specialist-tools explanation, and the
implementation-status-vs-specification distinction; forbids any fabricated accuracy/uptime/
client/production-adoption claim; and checks README links the guide.

Not applicable (pure documentation): unauthorized / stale-revision / dependency-failure cases —
the real failure surface is an unsupported claim or a missing section, asserted below.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GUIDE = REPO_ROOT / "docs" / "RECRUITER_GUIDE.md"
README = REPO_ROOT / "README.md"

REQUIRED_HEADINGS = [
    "## Overview",
    "architecture",
    "## Quick start",
    "## Demo paths",
    "## Tests",
    "## Trade-offs",
    "## Limitations",
    "## Implementation status vs specification",
]

# Fabricated claims that must never appear (measured mentions/negations are fine; these patterns
# only match an invented number or an adoption claim).
FORBIDDEN = [
    r"\d+\s?%\s*accuracy",
    r"\d+\s?%\s*uptime",
    r"99\.9\s?%",
    r"\bin production\b",
    r"\bour clients\b",
    r"\btrusted by\b",
    r"\bused by major\b",
]


class RecruiterGuide(unittest.TestCase):
    def setUp(self):
        self.assertTrue(GUIDE.exists(), "docs/RECRUITER_GUIDE.md must exist")
        self.text = GUIDE.read_text(encoding="utf-8")
        self.lower = self.text.lower()

    def test_required_sections_present(self):
        for heading in REQUIRED_HEADINGS:
            self.assertIn(heading.lower(), self.lower, f"missing section: {heading}")

    def test_explains_deterministic_decisions_and_specialist_tools(self):
        self.assertIn("deterministic", self.lower)
        self.assertIn("specialist tools", self.lower)

    def test_distinguishes_implementation_from_specification(self):
        self.assertIn("implemented", self.lower)
        self.assertIn("blocked", self.lower)
        self.assertIn("specification", self.lower)

    def test_links_measured_evidence(self):
        self.assertIn("SESSION_LOG.md", self.text)
        self.assertIn("HANDOVER.md", self.text)

    def test_no_invented_claims(self):
        for pattern in FORBIDDEN:
            self.assertIsNone(
                re.search(pattern, self.text, re.IGNORECASE),
                f"forbidden claim pattern present: {pattern}",
            )

    def test_readme_links_the_guide(self):
        self.assertTrue(README.exists())
        self.assertIn("docs/RECRUITER_GUIDE.md", README.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
