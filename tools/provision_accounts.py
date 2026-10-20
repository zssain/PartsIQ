"""Provision invited PartsIQ accounts in a Supabase project (idempotent, environment-targeted).

    uv run --all-packages python tools/provision_accounts.py --target dev --spec accounts.json [--links-only] [--dry-run]

* ``--target`` is REQUIRED (dev | staging). It must equal ``PARTSIQ_PROVISION_TARGET`` in the
  environment, so a shell pointed at another project cannot be used by accident.
* Production is refused: ``--target prod`` is rejected, and so is any run whose SUPABASE_URL
  matches ``PRODUCTION_SUPABASE_URL``. Production staff are invited one by one from the admin
  screen by a real administrator, never seeded.
* Reads SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY from the environment (never from arguments,
  never printed). No password is ever created, accepted or shown: users receive an invitation and
  choose their own password. ``--links-only`` prints a one-time invite link to THIS terminal for a
  secure hand-off instead of sending email (useful for a local Supabase without SMTP).
* Idempotent: existing users (by email) are not re-invited; their ``app_metadata.partsiq_roles``
  is reconciled to the spec.

The spec is a JSON list: ``[{"email": "...", "display_name": "...", "roles": ["reviewer"]}]``
(roles: reviewer, catalogue_admin, admin; an empty list is a customer). Keep real spec files out of
git (``accounts*.json`` is gitignored); see docs/examples/accounts.example.json.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

ALLOWED_ROLES = ("reviewer", "catalogue_admin", "admin")
TARGETS = ("dev", "staging")


def fail(message: str) -> None:
    print(f"refused: {message}", file=sys.stderr)
    raise SystemExit(2)


def load_spec(path: Path) -> list[dict]:
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read spec {path}: {exc}")
    if not isinstance(spec, list) or not spec:
        fail("spec must be a non-empty JSON list")
    seen = set()
    for entry in spec:
        email = str(entry.get("email", "")).strip().lower()
        if "@" not in email:
            fail(f"invalid email in spec: {email!r}")
        if email in seen:
            fail(f"duplicate email in spec: {email}")
        seen.add(email)
        roles = entry.get("roles", [])
        if not isinstance(roles, list) or any(r not in ALLOWED_ROLES for r in roles):
            fail(f"invalid roles for {email}: {roles}")
        if "password" in entry:
            fail("specs must not contain passwords; users set their own via the invitation")
    return spec


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--target", required=True, help="dev or staging (production is refused)")
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--links-only", action="store_true", help="print one-time invite links instead of emailing")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--redirect", default=os.environ.get("PARTSIQ_INVITE_REDIRECT", "http://localhost:3000/login?invited=1"))
    args = parser.parse_args(argv)

    if args.target not in TARGETS:
        fail("only dev or staging can be provisioned with this tool; production staff are invited from the admin screen")
    if os.environ.get("PARTSIQ_PROVISION_TARGET") != args.target:
        fail(f"set PARTSIQ_PROVISION_TARGET={args.target} in this shell to confirm the target environment")
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        fail("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in the environment")
    production = os.environ.get("PRODUCTION_SUPABASE_URL", "").rstrip("/")
    if production and production == url:
        fail("SUPABASE_URL is the production project")
    if os.environ.get("APP_ENV") == "prod":
        fail("APP_ENV=prod in this shell")

    spec = load_spec(args.spec)
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    with httpx.Client(base_url=f"{url}/auth/v1", headers=headers, timeout=10.0) as client:
        existing: dict[str, dict] = {}
        page = 1
        while True:
            response = client.get("/admin/users", params={"page": page, "per_page": 200})
            response.raise_for_status()
            users = response.json().get("users", [])
            existing.update({(u.get("email") or "").lower(): u for u in users})
            if len(users) < 200:
                break
            page += 1
        for entry in spec:
            email = entry["email"].strip().lower()
            roles = [r for r in ALLOWED_ROLES if r in entry.get("roles", [])]
            user = existing.get(email)
            if user is None:
                if args.dry_run:
                    print(f"would invite {email} roles={roles or ['customer']}")
                    continue
                if args.links_only:
                    response = client.post("/admin/generate_link", json={"type": "invite", "email": email, "redirect_to": args.redirect, "data": {"display_name": entry.get("display_name") or email.split("@")[0]}})
                    response.raise_for_status()
                    body = response.json()
                    user = body.get("user", body)
                    link = body.get("action_link") or body.get("properties", {}).get("action_link")
                    print(f"invite link for {email} (one-time, hand off securely): {link}")
                else:
                    response = client.post("/invite", params={"redirect_to": args.redirect}, json={"email": email, "data": {"display_name": entry.get("display_name") or email.split("@")[0]}})
                    response.raise_for_status()
                    user = response.json()
                    print(f"invited {email} (Supabase sent the email)")
            current = (user.get("app_metadata") or {}).get("partsiq_roles") or []
            if sorted(current) == sorted(roles):
                print(f"ok {email} roles={roles or ['customer']}")
                continue
            if args.dry_run:
                print(f"would set {email} roles {current} -> {roles}")
                continue
            meta = {**(user.get("app_metadata") or {}), "partsiq_roles": roles}
            client.put(f"/admin/users/{user['id']}", json={"app_metadata": meta}).raise_for_status()
            print(f"set {email} roles {current} -> {roles or ['customer']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
