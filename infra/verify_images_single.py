"""Static single-image compose verifier (prompt 24 — single-workflow edition).

Contract: ``def verify_images(compose_file: Path) -> list[str]``.

Returns a list of violation strings ([] means compliant) WITHOUT running Docker. It enforces
the single-workflow deployment invariants for infra/compose.production.yml:

  * application image tags are IMMUTABLE — an app image pins the release SHA
    (``ghcr.io/partsiq/...:${RELEASE_SHA}``) and base/infra images pin an ``@sha256`` digest
    (recorded in spec/images.lock.json); a mutable ``:latest`` (or any floating) tag is rejected;
  * every service declares a healthcheck;
  * only the public edge (``caddy``) may publish host ports, and only 80/443 — any other
    published port exposes an internal service (Redis/app must stay expose-only);
  * no embedded credential — a secret-named environment value must be a ``${VAR}`` reference,
    and no value may look like a literal API key.

This is the SINGLE-image sibling of infra/verify_images.py (which guards the earlier
multi-service docker-compose.prod.yml). Both are kept so neither build's tests break.
The digest manifest is read from spec/images.lock.json at the repository root.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]
_LOCK_PATH = _REPO_ROOT / "partsiq-build-kit" / "spec" / "images.lock.json"
_SECRET_HINTS = (
    "key",
    "secret",
    "token",
    "password",
    "authorization",
    "jwt",
    "credential",
    "dsn",
)
_VARREF = re.compile(r"^\$\{[A-Z0-9_]+(?::-[^}]*)?\}$")
_LOOKS_LIKE_KEY = re.compile(r"(sk-[A-Za-z0-9]{8,}|[A-Za-z0-9]{40,})")
_DIGEST = re.compile(r"@sha256:[a-f0-9]{64}$")
_PUBLIC_EDGE = "caddy"
_ALLOWED_PUBLIC_PORTS = {"80:80", "443:443", "80", "443"}


def _load_lock_digests() -> set[str]:
    """Return the set of pinned ``sha256:...`` digests recorded in the lock file."""
    if not _LOCK_PATH.exists():
        return set()
    data = json.loads(_LOCK_PATH.read_text(encoding="utf-8"))
    digests: set[str] = set()
    if isinstance(data, list):  # spec/images.lock.json is a list of {image,digest,pinned}
        for entry in data:
            digest = entry.get("digest")
            if digest:
                digests.add(str(digest))
    elif isinstance(data, dict):  # tolerate the {base_images: {...}} shape too
        for value in data.get("base_images", {}).values():
            digests.add(str(value))
    return digests


def _image_pinned(image: str, digests: set[str]) -> bool:
    """App image pins the immutable release SHA; a base/infra image pins a known @sha256."""
    if "${RELEASE_SHA}" in image:
        return True
    match = _DIGEST.search(image)
    if match:
        pinned = image.split("@", 1)[1]
        return not digests or pinned in digests
    return False


def _is_varref(value: str) -> bool:
    return bool(_VARREF.match(value))


def verify_images(compose_file: Path) -> list[str]:
    violations: list[str] = []
    digests = _load_lock_digests()
    try:
        compose = yaml.safe_load(Path(compose_file).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return [f"compose file unreadable: {type(exc).__name__}"]

    services = (compose or {}).get("services", {})
    if not services:
        return ["no services defined in compose file"]

    for name, svc in services.items():
        image = str(svc.get("image", ""))
        has_build = bool(svc.get("build"))
        if not image and not has_build:
            violations.append(f"{name}: no image pinned")
        elif image and (":latest" in image or image.endswith(":latest")):
            violations.append(f"{name}: mutable ':latest' tag")
        elif image and not _image_pinned(image, digests):
            violations.append(f"{name}: image not pinned to an immutable SHA/digest ({image})")

        if "healthcheck" not in svc:
            violations.append(f"{name}: missing healthcheck")

        ports = svc.get("ports") or []
        if ports and name != _PUBLIC_EDGE:
            violations.append(f"{name}: publishes host ports {ports} (only {_PUBLIC_EDGE} may)")
        if name == _PUBLIC_EDGE:
            for mapping in ports:
                if str(mapping).strip().strip('"') not in _ALLOWED_PUBLIC_PORTS:
                    violations.append(f"{name}: non-edge published port {mapping}")

        env = svc.get("environment") or {}
        if isinstance(env, dict):
            items = env.items()
        else:
            items = (tuple(e.split("=", 1)) for e in env if "=" in e)
        for key, value in items:
            value = str(value)
            lowered = str(key).lower()
            if any(hint in lowered for hint in _SECRET_HINTS) and value and not _is_varref(value):
                violations.append(f"{name}: environment {key} has a literal value (use ${{VAR}})")
            elif _LOOKS_LIKE_KEY.search(value) and not _is_varref(value):
                violations.append(f"{name}: environment {key} looks like an embedded credential")

    return violations


if __name__ == "__main__":  # pragma: no cover - manual invocation
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else _REPO_ROOT / "infra" / "compose.production.yml"
    found = verify_images(target)
    if found:
        print(f"{target}: {len(found)} violation(s)")
        for item in found:
            print(f"  - {item}")
        sys.exit(1)
    print(f"{target}: OK (no violations)")
