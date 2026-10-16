"""Acceptance tests for prompt 20 — staff workspace and timeline (foundation gate).

run_checks dispatches this stdlib structural gate; the React behaviour is covered by the
vitest suite (apps/web/tests/features/f18 + f27 + f37). Here we assert the review components
exist and encode the invariants regardless of runtime: the workspace assembles every panel
with explicit empty states and keeps staff notes separate from customer messages; approve is
gated on a current verified state and posts the expected revision + an idempotency key, with
a 409 forcing a reload; reject requires a reason; scores are a match score, not a calibrated
probability; and the timeline separates customer vs staff waits without fabricating
completion. Covers F03, F18, F27, F32, F37, F39, F53, F61 (web half).
"""
from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB = REPO_ROOT / "apps" / "web"


def _read(rel: str) -> str:
    return (WEB / rel).read_text(encoding="utf-8")


class Files(unittest.TestCase):
    def test_required_files_exist(self):
        for rel in (
            "app/staff/inbox/page.tsx", "app/staff/enquiries/[id]/page.tsx",
            "components/review/Workspace.tsx", "components/review/ApprovalControls.tsx",
            "components/review/Timeline.tsx", "tests/features/f18.test.tsx",
            "tests/features/f27.test.tsx", "tests/features/f37.test.tsx",
        ):
            self.assertTrue((WEB / rel).exists(), f"missing {rel}")


class Workspace(unittest.TestCase):
    def test_assembles_panels_with_empty_states(self):
        ws = _read("components/review/Workspace.tsx")
        for empty in ("candidates-empty", "verification-empty", "draft-empty", "notes-empty"):
            self.assertIn(empty, ws)
        self.assertIn("Internal notes (staff only)", ws)   # staff-only notes panel
        self.assertIn("Customer conversation", ws)          # separate from notes

    def test_match_score_not_probability(self):  # F27
        ws = _read("components/review/Workspace.tsx")
        self.assertIn("Match score", ws)
        self.assertNotIn("probability", ws.lower())

    def test_stock_shows_available_warehouse_and_timestamp(self):  # F32 display
        ws = _read("components/review/Workspace.tsx")
        self.assertIn("s.available", ws)
        self.assertIn("s.warehouse_id", ws)
        self.assertIn("s.updated_at", ws)

    def test_absent_evidence_shown_unavailable(self):  # F27
        self.assertIn("Evidence unavailable", _read("components/review/Workspace.tsx"))


class ApprovalControls(unittest.TestCase):
    def test_approve_gated_on_current_verified(self):  # F37/F39
        ac = _read("components/review/ApprovalControls.tsx")
        self.assertIn("verification?.passed", ac)
        self.assertIn('status === "awaiting_review"', ac)

    def test_posts_expected_revision_and_idempotency_key(self):
        ac = _read("components/review/ApprovalControls.tsx")
        self.assertIn("expected_revision", ac)
        self.assertIn("idempotency-key", ac)

    def test_409_forces_reload_and_reject_requires_reason(self):  # stale-revision + F39
        ac = _read("components/review/ApprovalControls.tsx")
        self.assertIn("409", ac)
        self.assertIn("reason.trim().length === 0", ac)

    def test_pdf_action_present(self):  # F61
        self.assertIn("export", _read("components/review/ApprovalControls.tsx").lower())


class Timeline(unittest.TestCase):
    def test_customer_vs_staff_wait(self):  # F18
        tl = _read("components/review/Timeline.tsx")
        self.assertIn("needs_information", tl)
        self.assertIn("awaiting_review", tl)

    def test_no_fabricated_completion(self):
        tl = _read("components/review/Timeline.tsx")
        self.assertIn("REACHED_BY", tl)      # stage reached is derived from real status
        self.assertIn("data-reached", tl)


if __name__ == "__main__":
    unittest.main(verbosity=2)
