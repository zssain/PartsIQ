"""Static production-image/compose verifier (prompt 24).

Contract: ``def verify_images(compose_file: Path) -> list[str]``.

Returns a list of violation strings ([] means compliant) WITHOUT running Docker:
  * mutable application tags are rejected — app images must pin an immutable release SHA
    and infra/base images must pin an @sha256 digest (from infra/images.lock.json);
  * every service must declare a healthcheck;
  * only the public edge (caddy) may publish host ports, and only 80/443 — any other
    published port exposes an internal service;
  * no embedded credential — a secret-named environment value must be a ${VAR} reference,
    and no value may look like a literal API key.
The digest manifest is read from infra/images.lock.json next to this file.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

_LOCK_PATH = Path(__file__).with_name("images.lock.json")
_SECRET_HINTS = ("key", "secret", "token", "password", "authorization", "jwt", "credential", "dsn", "url")
_VARREF = re.compile(r"^\$\{[A-Z0-9_]+\}$")
_LOOKS_LIKE_KEY = re.compile(r"(sk-[A-Za-z0-9]{8,}|[A-Za-z0-9]{40,})")
_DIGEST = re.compile(r"@sha256:[a-f0-9]{64}$")
_PUBLIC_EDGE = "caddy"
_ALLOWED_PUBLIC_PORTS = {"80:80", "443:443", "80", "443"}


def _load_lock() -> dict:
    if not _LOCK_PATH.exists():
        return {}
    return json.loads(_LOCK_PATH.read_text(encoding="utf-8"))


def _image_pinned(image: str, lock: dict) -> bool:
    """An app image pins the immutable release SHA; a base/infra image pins an @sha256 digest."""
    if "${RELEASE_SHA}" in image:
        return True
    if _DIGEST.search(image):
        digests = set(_load_lock().get("base_images", {}).values()) if not lock else set(lock.get("base_images", {}).values())
        pinned = image.split("@", 1)[1]
        return pinned in digests
    return False


def verify_images(compose_file: Path) -> list[str]:
    violations: list[str] = []
    lock = _load_lock()
    try:
        compose = yaml.safe_load(compose_file.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return [f"compose file unreadable: {type(exc).__name__}"]

    services = (compose or {}).get("services", {})
    if not services:
        return ["no services defined in compose file"]

    for name, svc in services.items():
        image = str(svc.get("image", ""))
        if not image:
            violations.append(f"{name}: no image pinned")
        elif ":latest" in image or image.endswith(":latest"):
            violations.append(f"{name}: mutable ':latest' tag")
        elif not _image_pinned(image, lock):
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
        items = env.items() if isinstance(env, dict) else (e.split("=", 1) for e in env if "=" in e)
        for key, value in items:
            value = str(value)
            lowered = str(key).lower()
            if any(hint in lowered for hint in _SECRET_HINTS) and value and not _VARREF.match(value):
                violations.append(f"{name}: environment {key} has a literal value (use ${{VAR}})")
            elif _LOOKS_LIKE_KEY.search(value) and not _VARREF.match(value):
                violations.append(f"{name}: environment {key} looks like an embedded credential")

    return violations
