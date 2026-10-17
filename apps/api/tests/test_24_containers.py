"""Foundation 24 acceptance: ONE application image, worker and Caddy (single-workflow edition).

Fully offline static assertions over the owned deployment artifacts — building/pushing/running
images needs Docker and a registry and is BLOCKED here. We parse the YAML/text of the files and
the owned verifier; nothing is mocked away.

Owned files under test:
  * apps/api/Dockerfile          — one multi-stage image; API default command (uvicorn factory)
                                   and worker command (python -m partsiq.jobs.main) from one image;
                                   non-root; base pinned by @sha256 digest.
  * infra/Caddyfile              — the ONLY public ingress; auto-TLS for ${API_DOMAIN}; HSTS +
                                   nosniff + DENY headers; reverse_proxy to api:8000 with /health probe.
  * infra/compose.production.yml — only Caddy publishes 80/443; api/worker/sweeper/redis are
                                   expose-only; immutable ${RELEASE_SHA} app tag + @sha256 base
                                   digests; read-only rootfs + tmpfs for PDF; resource limits;
                                   secrets only as ${VAR}; separate api vs worker commands.
  * infra/compose.fixture.yml    — labelled no-provider profile (DATA_SOURCE=fixture, AI_MODE=fixture),
                                   no OpenAI/Snowflake credentials, local port bound to 127.0.0.1.
  * tools/healthcheck.py         — credit-free local /health probe used by the image HEALTHCHECK.
  * infra/verify_images_single.py — static verifier; we assert it accepts the clean production
                                   compose and catches each violation class.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]

DOCKERFILE = REPO_ROOT / "apps" / "api" / "Dockerfile"
CADDYFILE = REPO_ROOT / "infra" / "Caddyfile"
PROD_COMPOSE = REPO_ROOT / "infra" / "compose.production.yml"
FIXTURE_COMPOSE = REPO_ROOT / "infra" / "compose.fixture.yml"
HEALTHCHECK = REPO_ROOT / "tools" / "healthcheck.py"
VERIFIER = REPO_ROOT / "infra" / "verify_images_single.py"


def _load_verifier():
    spec = importlib.util.spec_from_file_location("partsiq_verify_images_single", VERIFIER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _compose(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class FilesExist(unittest.TestCase):
    def test_all_owned_files_present(self):
        for path in (DOCKERFILE, CADDYFILE, PROD_COMPOSE, FIXTURE_COMPOSE, HEALTHCHECK, VERIFIER):
            self.assertTrue(path.exists(), f"missing owned file: {path}")


class Dockerfile(unittest.TestCase):
    def setUp(self):
        self.text = DOCKERFILE.read_text(encoding="utf-8")

    def test_base_pinned_by_digest(self):
        self.assertRegex(self.text, r"FROM python:3\.12[.\d]*-slim[\w-]*@sha256:[a-f0-9]{64}")

    def test_non_root_user(self):
        self.assertIn("useradd", self.text)
        self.assertRegex(self.text, r"USER\s+appuser")

    def test_api_command_is_uvicorn_factory(self):
        # One image: the DEFAULT command runs the API factory on 0.0.0.0:8000 with one worker.
        self.assertIn("partsiq.main:create_app", self.text)
        self.assertIn("--factory", self.text)
        self.assertIn("uvicorn", self.text)

    def test_worker_entrypoint_is_referenced(self):
        # The SAME image runs the worker via a different command; the module must be reachable.
        self.assertIn("partsiq.jobs.main", self.text)

    def test_frozen_dependencies(self):
        self.assertIn("python-requirements.lock", self.text)

    def test_healthcheck_declared(self):
        self.assertIn("HEALTHCHECK", self.text)


class Caddy(unittest.TestCase):
    def setUp(self):
        self.text = CADDYFILE.read_text(encoding="utf-8")

    def test_auto_tls_for_api_domain(self):
        self.assertIn("{$API_DOMAIN}", self.text)

    def test_security_headers(self):
        self.assertIn("Strict-Transport-Security", self.text)
        self.assertIn("X-Content-Type-Options", self.text)
        self.assertIn('X-Frame-Options "DENY"', self.text)

    def test_reverse_proxy_to_api_with_health_probe(self):
        self.assertIn("reverse_proxy api:8000", self.text)
        self.assertIn("health_uri /health", self.text)


class ProductionCompose(unittest.TestCase):
    def setUp(self):
        self.compose = _compose(PROD_COMPOSE)
        self.services = self.compose["services"]

    def test_only_caddy_publishes_ports(self):
        for name, svc in self.services.items():
            if name != "caddy":
                self.assertNotIn("ports", svc, f"{name} must not publish host ports")
        self.assertEqual(
            sorted(str(p) for p in self.services["caddy"]["ports"]),
            ["443:443", "80:80"],
        )

    def test_redis_and_app_are_expose_only(self):
        for name in ("api", "worker", "sweeper", "redis"):
            svc = self.services[name]
            self.assertNotIn("ports", svc, f"{name} must not publish host ports")

    def test_immutable_app_tags(self):
        for name in ("api", "worker", "sweeper"):
            self.assertIn("${RELEASE_SHA}", self.services[name]["image"], name)
            self.assertNotIn(":latest", self.services[name]["image"], name)

    def test_base_images_pin_digest(self):
        self.assertRegex(self.services["caddy"]["image"], r"@sha256:[a-f0-9]{64}")
        self.assertRegex(self.services["redis"]["image"], r"@sha256:[a-f0-9]{64}")

    def test_single_image_shared_by_api_and_worker(self):
        api_img = self.services["api"]["image"]
        worker_img = self.services["worker"]["image"]
        self.assertEqual(api_img, worker_img, "api and worker must run the SAME image")

    def test_separate_api_and_worker_commands(self):
        self.assertIn("partsiq.main:create_app", " ".join(self.services["api"]["command"]))
        self.assertIn("partsiq.jobs.main", " ".join(self.services["worker"]["command"]))

    def test_every_service_has_healthcheck(self):
        for name, svc in self.services.items():
            self.assertIn("healthcheck", svc, f"{name} missing healthcheck")

    def test_resource_limits_present(self):
        for name, svc in self.services.items():
            self.assertIn("limits", svc["deploy"]["resources"], f"{name} missing limits")

    def test_worker_has_pdf_tmpfs(self):
        self.assertIn("/tmp/pdf", self.services["worker"]["tmpfs"])

    def test_read_only_rootfs_where_possible(self):
        self.assertTrue(self.services["api"].get("read_only"))
        self.assertTrue(self.services["worker"].get("read_only"))

    def test_no_embedded_secret_literals(self):
        # Every environment value either is a ${VAR} ref or a non-secret scalar/default.
        for name, svc in self.services.items():
            for key, value in (svc.get("environment") or {}).items():
                if any(h in key.lower() for h in ("key", "secret", "token", "password", "jwt")):
                    self.assertIn("${", str(value), f"{name}.{key} must be a ${{VAR}} reference")

    def test_semantic_profile_is_optional_and_worker_only(self):
        semantic = self.services.get("worker-semantic")
        self.assertIsNotNone(semantic, "optional semantic worker profile must exist")
        self.assertIn("semantic", semantic.get("profiles", []))
        self.assertEqual(semantic["environment"]["SEMANTIC_SEARCH_ENABLED"], "true")
        # A measured RAM reservation, not a free-tier promise.
        self.assertIn("reservations", semantic["deploy"]["resources"])


class FixtureCompose(unittest.TestCase):
    def setUp(self):
        self.compose = _compose(FIXTURE_COMPOSE)
        self.services = self.compose["services"]

    def test_labelled_no_provider_profile(self):
        api_env = self.services["api"]["environment"]
        self.assertEqual(api_env["DATA_SOURCE"], "fixture")
        self.assertEqual(api_env["AI_MODE"], "fixture")
        worker_env = self.services["worker"]["environment"]
        self.assertEqual(worker_env["DATA_SOURCE"], "fixture")
        self.assertEqual(worker_env["AI_MODE"], "fixture")

    def test_no_provider_credentials(self):
        for name in ("api", "worker"):
            env = self.services[name]["environment"]
            for banned in ("OPENAI_API_KEY", "SNOWFLAKE_ACCOUNT", "SNOWFLAKE_PRIVATE_KEY_FILE"):
                self.assertNotIn(banned, env, f"{name} fixture profile must not set {banned}")

    def test_local_port_bound_to_loopback(self):
        ports = [str(p) for p in self.services["api"]["ports"]]
        self.assertTrue(all(p.startswith("127.0.0.1:") for p in ports), ports)

    def test_redis_not_published(self):
        self.assertNotIn("ports", self.services["redis"])

    def test_separate_api_and_worker_commands(self):
        self.assertIn("partsiq.main:create_app", " ".join(self.services["api"]["command"]))
        self.assertIn("partsiq.jobs.main", " ".join(self.services["worker"]["command"]))


_BAD_COMPOSE = """
name: bad
services:
  api:
    image: ghcr.io/partsiq/partsiq:latest
    ports:
      - "8000:8000"
    environment:
      OPENAI_API_KEY: sk-abcdef0123456789abcdef0123456789
  redis:
    image: redis:7.4-alpine
"""


class Verifier(unittest.TestCase):
    def setUp(self):
        self.module = _load_verifier()

    def test_production_compose_is_clean(self):
        self.assertEqual(self.module.verify_images(PROD_COMPOSE), [])

    def test_catches_every_violation_class(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.yml"
            bad.write_text(_BAD_COMPOSE, encoding="utf-8")
            violations = self.module.verify_images(bad)
        joined = " ".join(violations)
        self.assertIn("latest", joined)  # mutable application tag
        self.assertIn("host ports", joined)  # internal service publishing a host port
        self.assertIn("missing healthcheck", joined)  # no healthcheck
        self.assertTrue(
            "embedded credential" in joined or "literal value" in joined,
            f"secret not caught: {joined}",
        )

    def test_fixture_loopback_ports_are_rejected_by_edge_rule(self):
        # The fixture profile intentionally binds a dev port on the api service; the production
        # verifier (edge-only publishing) flags it, which is why fixture is a SEPARATE file.
        violations = self.module.verify_images(FIXTURE_COMPOSE)
        self.assertTrue(any("host ports" in v for v in violations), violations)


if __name__ == "__main__":
    unittest.main(verbosity=2)
