"""F69 Demo walkthrough — 3- and 8-minute scripts + recording checklist, no false video claim.

Both scripts cover happy path / missing serial / incompatibility / stock split / human review,
carry captions, use synthetic data, and show failure handling + reset. The checklist requires
verifying links. No document claims a video already exists.

Not applicable (pure documentation): unauthorized / stale-revision / dependency-failure.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "docs" / "DEMO_SCRIPT.md"
CHECKLIST = REPO_ROOT / "docs" / "RECORDING_CHECKLIST.md"

SCENARIOS = ["happy path", "missing serial", "incompatib", "stock split", "human review"]

# A claim that a recording already exists must never appear.
FORBIDDEN_VIDEO_CLAIMS = [
    r"watch the (video|recording)",
    r"(video|recording) is available",
    r"https?://\S+\.mp4",
    r"https?://(www\.)?(youtube|youtu\.be|vimeo)\b",
]


class DemoScript(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.exists(), "docs/DEMO_SCRIPT.md must exist")
        self.text = SCRIPT.read_text(encoding="utf-8")
        self.lower = self.text.lower()

    def test_has_both_scripts(self):
        self.assertIn("3-minute", self.lower)
        self.assertIn("8-minute", self.lower)

    def test_covers_all_scenarios(self):
        for scenario in SCENARIOS:
            self.assertIn(scenario, self.lower, f"script missing scenario: {scenario}")

    def test_has_captions(self):
        self.assertIn("caption", self.lower)

    def test_uses_synthetic_data_and_shows_failure_and_reset(self):
        self.assertIn("synthetic", self.lower)
        self.assertIn("failure handling", self.lower)
        self.assertIn("reset", self.lower)

    def test_no_false_video_claim(self):
        for pattern in FORBIDDEN_VIDEO_CLAIMS:
            self.assertIsNone(re.search(pattern, self.text, re.IGNORECASE), f"false video claim: {pattern}")
        self.assertIn("no video exists yet", self.lower)


class RecordingChecklist(unittest.TestCase):
    def setUp(self):
        self.assertTrue(CHECKLIST.exists(), "docs/RECORDING_CHECKLIST.md must exist")
        self.text = CHECKLIST.read_text(encoding="utf-8")
        self.lower = self.text.lower()

    def test_requires_synthetic_links_failure_reset(self):
        self.assertIn("synthetic", self.lower)
        self.assertIn("verify every link", self.lower)
        self.assertIn("failure handling", self.lower)
        self.assertIn("reset", self.lower)

    def test_does_not_claim_a_video_exists(self):
        for pattern in FORBIDDEN_VIDEO_CLAIMS:
            self.assertIsNone(re.search(pattern, self.text, re.IGNORECASE), f"false video claim: {pattern}")
        self.assertIn("do not claim a video", self.lower)


if __name__ == "__main__":
    unittest.main(verbosity=2)
