"""Acceptance tests for prompt 24 — production containers and Caddy (foundation gate).

verify_images statically rejects mutable application tags, missing healthchecks, public
internal ports and embedded credentials. The committed docker-compose.prod.yml is clean, and
a crafted bad compose trips each check. The orchestrator/worker/gateway/search Dockerfiles
pin their base by @sha256 digest, and only Caddy publishes host ports (80/443).
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from infra.verify_images import verify_images  # noqa: E402

PROD_COMPOSE = REPO_ROOT / "docker-compose.prod.yml"

_BAD = """
name: bad
services:
  gateway:
    image: ghcr.io/partsiq/gateway:latest
    ports:
      - "8000:8000"
    environment:
      OPENAI_API_KEY: sk-abcdef0123456789abcdef0123456789
  redis:
    image: redis:7.3-alpine
"""


class VerifyImages(unittest.TestCase):
    def test_production_compose_is_clean(self):
        self.assertEqual(verify_images(PROD_COMPOSE), [])

    def test_catches_all_violation_classes(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.yml"
            bad.write_text(_BAD, encoding="utf-8")
            violations = verify_images(bad)
        joined = " ".join(violations)
        self.assertIn("latest", joined)                    # mutable tag
        self.assertIn("host ports", joined)                # internal service publishing
        self.assertTrue("embedded credential" in joined or "literal value" in joined)  # secret
        self.assertIn("missing healthcheck", joined)       # no healthcheck


class Dockerfiles(unittest.TestCase):
    def test_all_service_dockerfiles_pin_base_digest(self):
        for rel in (
            "services/gateway/Dockerfile", "services/search/Dockerfile",
            "services/orchestrator/Dockerfile", "services/worker/Dockerfile",
        ):
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
            self.assertRegex(text, r"FROM python:3\.12-slim@sha256:[a-f0-9]{64}", rel)


class Compose(unittest.TestCase):
    def test_only_caddy_publishes_ports(self):
        import yaml

        compose = yaml.safe_load(PROD_COMPOSE.read_text(encoding="utf-8"))
        for name, svc in compose["services"].items():
            if name != "caddy":
                self.assertNotIn("ports", svc, f"{name} must not publish host ports")
        self.assertEqual(sorted(str(p) for p in compose["services"]["caddy"]["ports"]), ["443:443", "80:80"])

    def test_separate_worker_sweeper_and_consumer_commands(self):
        import yaml

        services = yaml.safe_load(PROD_COMPOSE.read_text(encoding="utf-8"))["services"]
        self.assertIn("app.sweeper", " ".join(services["sweeper"]["command"]))
        self.assertIn("app.dispatcher", " ".join(services["worker"]["command"]))
        self.assertIn("app.runner", " ".join(services["orchestrator-consumer"]["command"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
