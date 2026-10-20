"""Acceptance tests for prompt 18 — frontend shell and authentication (foundation gate).

run_checks dispatches this stdlib structural gate; the React behaviour is covered by the
vitest suite (apps/web/tests/features/f01.test.tsx — 4 passed) which needs the pnpm
toolchain. Here we assert the manifest pins, required files, and the security invariants that
must hold regardless of the runtime: the bearer token travels in the Authorization header
(never the URL), only public NEXT_PUBLIC_* Supabase values are used in the browser, no secret
appears in apps/web, and there is no public real-client signup. Covers F01, F54 (web half).
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB = REPO_ROOT / "apps" / "web"


def _read(rel: str) -> str:
    return (WEB / rel).read_text(encoding="utf-8")


class Manifest(unittest.TestCase):
    def test_package_json_pins(self):
        pkg = json.loads(_read("package.json"))
        self.assertTrue(pkg["private"])
        self.assertEqual(pkg["dependencies"]["next"], "16.2.12")
        self.assertEqual(pkg["dependencies"]["react"], "19.2.6")
        self.assertEqual(pkg["dependencies"]["@supabase/ssr"], "0.8.0")
        self.assertEqual(pkg["devDependencies"]["vitest"], "4.1.11")
        self.assertEqual(pkg["devDependencies"]["typescript"], "5.9.3")

    def test_required_files_exist(self):
        for rel in (
            "tsconfig.json", "next.config.ts", "postcss.config.mjs", "eslint.config.mjs",
            "vitest.config.ts", "app/layout.tsx", "app/page.tsx", "app/login/page.tsx",
            "styles/tokens.css", "lib/api.ts", "lib/auth.ts", "lib/contracts.ts",
            "components/BrandLogo.tsx", "pnpm-lock.yaml", "tests/setup.ts",
            "playwright.config.ts", "tests/features/f01.test.tsx",
        ):
            self.assertTrue((WEB / rel).exists(), f"missing {rel}")

    def test_brand_logo_asset_bundled(self):
        self.assertTrue((WEB / "public" / "brand" / "logo-original.png").exists())


class Security(unittest.TestCase):
    def test_bearer_in_header_not_url(self):
        api = _read("lib/api.ts")
        self.assertIn("authorization", api.lower())
        self.assertIn("Bearer", api)
        # The access token must never be placed in the URL/query string.
        self.assertNotRegex(api, r"[?&](access_token|token)=")

    def test_browser_uses_only_public_supabase_values(self):
        auth = _read("lib/auth.ts")
        self.assertIn("NEXT_PUBLIC_SUPABASE_URL", auth)
        self.assertIn("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY", auth)

    def test_no_secret_in_web_source(self):
        banned = ("SERVICE_ROLE", "SUPABASE_JWT", "SUPABASE_STORAGE_KEY", "INTERNAL_SERVICE_TOKEN", "OPENAI_API_KEY")
        for path in WEB.rglob("*.ts*"):
            if "node_modules" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            for secret in banned:
                self.assertNotIn(secret, text, f"{secret} leaked in {path.relative_to(WEB)}")

    def test_no_public_real_client_signup(self):
        login = _read("app/login/page.tsx")
        self.assertNotIn("signUp", login)             # no self-signup call
        self.assertIn("There is no public signup", login)
        # The email-link path must never create an account for an unknown address.
        self.assertIn("shouldCreateUser: false", login)


class Landing(unittest.TestCase):
    def test_synthetic_notice_and_no_affiliation(self):
        page = re.sub(r"\s+", " ", _read("app/page.tsx").lower())  # collapse wrapping whitespace
        self.assertIn("synthetic", page)
        self.assertIn("not affiliated", page)

    def test_repo_link_is_conditional(self):
        page = _read("app/page.tsx")
        self.assertIn("NEXT_PUBLIC_REPO_URL", page)
        self.assertTrue(re.search(r"REPO_URL\s*\?", page), "repo link must be hidden when unconfigured")

    def test_logo_has_alt_text(self):
        self.assertRegex(_read("components/BrandLogo.tsx"), r'alt=')


if __name__ == "__main__":
    unittest.main(verbosity=2)
