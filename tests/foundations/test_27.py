"""Acceptance tests for prompt 27 — Vercel and hosted acceptance (foundation gate).

run_hosted_acceptance rejects non-HTTPS URLs outside localhost, refuses to claim availability
with no hosted client wired, and otherwise reports exactly which of the four demo scenarios
passed/failed — the deployment is available ONLY when all four pass. The real hosted run (and
the Playwright hosted spec) are BLOCKED until a live deployment exists. The Vercel README keeps
only publishable values public and forbids wildcard CORS.
"""
from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "libs" / "partsiq_common"))

from partsiq_common.errors import PartsIQError  # noqa: E402
from tools.hosted_acceptance import SCENARIOS, is_available, run_hosted_acceptance  # noqa: E402

NOW = datetime(2026, 10, 17, tzinfo=UTC)
HTTPS_BASE = "https://partsiq.example.com"
HTTPS_API = "https://api.partsiq.example.com"


def _check(passing: set[str]):
    async def check(_api_url, scenario):
        return scenario in passing

    return check


class HostedAcceptance(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_https_url(self):
        with self.assertRaises(PartsIQError) as ctx:
            await run_hosted_acceptance("http://partsiq.example.com", HTTPS_API, check=_check(set(SCENARIOS)), now=NOW)
        self.assertEqual(ctx.exception.code, "MALFORMED_REQUEST")

    async def test_allows_localhost_http(self):
        receipt = await run_hosted_acceptance("http://localhost:3000", "http://localhost:8000",
                                              check=_check(set(SCENARIOS)), now=NOW)
        self.assertTrue(is_available(receipt))

    async def test_no_client_refuses_to_claim_available(self):
        with self.assertRaises(PartsIQError) as ctx:
            await run_hosted_acceptance(HTTPS_BASE, HTTPS_API, now=NOW)
        self.assertEqual(ctx.exception.code, "DEPENDENCY_UNAVAILABLE")

    async def test_all_four_pass_is_available(self):
        receipt = await run_hosted_acceptance(HTTPS_BASE, HTTPS_API, check=_check(set(SCENARIOS)), now=NOW)
        self.assertEqual(sorted(receipt.scenarios_passed), sorted(SCENARIOS))
        self.assertEqual(receipt.scenarios_failed, [])
        self.assertTrue(is_available(receipt))

    async def test_any_failure_blocks_availability(self):
        receipt = await run_hosted_acceptance(HTTPS_BASE, HTTPS_API,
                                              check=_check(set(SCENARIOS) - {"local_shortage"}), now=NOW)
        self.assertIn("local_shortage", receipt.scenarios_failed)
        self.assertFalse(is_available(receipt))  # not claimed available unless ALL pass


class VercelReadme(unittest.TestCase):
    def _text(self):
        return (REPO_ROOT / "infra" / "vercel" / "README.md").read_text(encoding="utf-8")

    def test_only_public_values_are_public(self):
        text = self._text()
        self.assertIn("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY", text)
        self.assertIn("not** a secret", text)  # publishable key explicitly noted as non-secret

    def test_forbids_wildcard_cors(self):
        self.assertIn("no wildcard", self._text().lower())

    def test_documents_free_tier_limits(self):
        text = self._text().lower()
        self.assertIn("inactivity pausing", text)
        self.assertIn("credit expir", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
