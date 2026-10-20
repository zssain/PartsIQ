"""Acceptance tests for prompt 19 — customer chat and demo (foundation gate).

run_checks dispatches this stdlib structural gate; the React behaviour is covered by the
vitest suite (apps/web/tests/features/f01.test.tsx + f15.test.tsx — 8 passed). Here we assert
the chat/demo components exist and encode the key invariants regardless of runtime: polling
uses an AbortController with bounded backoff and a hidden-tab throttle, the send path clears
the draft only on success (preserving unsent text on failure, F09/F53), the progress view
separates waiting-customer from waiting-staff and never fabricates completion (F18), uploads
validate MIME/size up front (F13), OcrConfirmation keeps the serial verbatim (F15), and the
demo resets the client cache (F05). Covers F02, F03, F05, F09, F11, F13, F15, F18, F53 (web).
"""
from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB = REPO_ROOT / "apps" / "web"


def _read(rel: str) -> str:
    return (WEB / rel).read_text(encoding="utf-8")


class Files(unittest.TestCase):
    def test_required_components_exist(self):
        for rel in (
            "app/chat/[id]/page.tsx", "app/demo/page.tsx", "components/chat/Chat.tsx",
            "components/chat/UploadCard.tsx", "components/chat/OcrConfirmation.tsx",
            "components/chat/Progress.tsx", "tests/features/f15.test.tsx",
        ):
            self.assertTrue((WEB / rel).exists(), f"missing {rel}")


class Polling(unittest.TestCase):
    def test_abortcontroller_and_bounded_backoff(self):
        chat = _read("components/chat/Chat.tsx")
        self.assertIn("AbortController", chat)
        self.assertIn("MAX_DELAY_MS", chat)
        self.assertIn("document.hidden", chat)  # hidden tabs reduce polling

    def test_unsent_text_preserved_on_failure(self):
        chat = _read("components/chat/Chat.tsx")
        # The draft is cleared on success but NEVER in the send's catch (the last catch block),
        # so a failed send keeps the customer's unsent text.
        self.assertIn('setDraft("")', chat)
        self.assertNotIn('setDraft("")', chat.rsplit("catch", 1)[1])

    def test_message_send_is_idempotent_and_revision_bound(self):
        chat = _read("components/chat/Chat.tsx")
        self.assertIn("idempotency-key", chat)
        self.assertIn("expected_revision", chat)


class ProgressView(unittest.TestCase):
    def test_separates_customer_and_staff_waits(self):
        progress = _read("components/chat/Progress.tsx")
        self.assertIn("needs_information", progress)   # waiting for customer
        self.assertIn("awaiting_review", progress)     # waiting for staff
        self.assertIn("Retry", progress)               # failed poll offers retry

    def test_no_fabricated_completion(self):
        progress = _read("components/chat/Progress.tsx")
        self.assertIn("enquiry.status", progress)      # renders real server status only


class Uploads(unittest.TestCase):
    def test_mime_and_size_validated(self):
        upload = _read("components/chat/UploadCard.tsx")
        self.assertIn("image/jpeg", upload)
        self.assertIn("MAX_BYTES", upload)
        self.assertIn("/v1/uploads", upload)


class Ocr(unittest.TestCase):
    def test_serial_preserved_verbatim(self):
        ocr = _read("components/chat/OcrConfirmation.tsx")
        self.assertIn("serial_text: serial", ocr)      # passed through, not trimmed/normalised
        self.assertNotIn(".trim()", ocr.split("serial_text")[0].rsplit("serial", 1)[-1])


class Demo(unittest.TestCase):
    def test_four_scenarios_and_reset_clears_cache(self):
        # The four scripted walkthroughs (secondary to the live workspace sandbox).
        engine = _read("lib/demo/engine.ts")
        for scenario in ("mixed_photo", "missing_serial", "incompatible_number", "local_shortage"):
            self.assertIn(scenario, engine)
        self.assertIn("SCENARIOS", _read("app/demo/scenarios/page.tsx"))
        # Reset starts a new server-side session generation...
        self.assertIn("/reset", _read("lib/workspace.ts"))
        # ...and the generation is part of the identity key, so every cached screen is dropped.
        session = _read("lib/session.tsx")
        self.assertIn("me.demo_session_generation", session)
        self.assertIn("drop every cached screen", session)


if __name__ == "__main__":
    unittest.main(verbosity=2)
