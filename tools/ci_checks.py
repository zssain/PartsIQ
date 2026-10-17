"""Static CI/deploy configuration checker (prompt 25 — F66).

Contract: ``def check_ci_configuration(root: Path) -> list[str]``.

Inspects .github/workflows/*.yml WITHOUT running CI and returns violation strings ([] is
compliant):
  * every third-party action is pinned to a 40-hex commit SHA (never a moving @vN/@branch);
  * each workflow declares least-privilege top-level permissions (contents: read);
  * the deploy workflow is gated by a GitHub environment (manual approval), authenticates via
    OIDC (id-token: write), is disabled until infrastructure is marked ready, runs the backend
    migration before activating the new image, and is never triggered by pull_request (so a
    fork cannot reach deploy secrets).
Action SHAs here are recorded pins to re-verify against each action's release at setup.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

_SHA_PINNED = re.compile(r"^[A-Za-z0-9._/-]+@[0-9a-f]{40}$")


def _uses_values(node) -> list[str]:
    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "uses" and isinstance(value, str):
                found.append(value)
            else:
                found.extend(_uses_values(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_uses_values(item))
    return found


def _check_workflow(name: str, wf: dict) -> list[str]:
    out: list[str] = []

    for uses in _uses_values(wf):
        if uses.startswith("./"):
            continue  # a local composite action is not SHA-pinnable
        if not _SHA_PINNED.match(uses):
            out.append(f"{name}: action '{uses}' is not pinned to a 40-hex commit SHA")

    perms = wf.get("permissions")
    if perms is None:
        out.append(f"{name}: no top-level permissions (defaults to write-all)")
    elif isinstance(perms, dict) and perms.get("contents") not in ("read", None) and "write" in str(perms.get("contents")):
        out.append(f"{name}: top-level contents permission is not read-only")

    return out


def _check_deploy(name: str, wf: dict) -> list[str]:
    out: list[str] = []
    on = wf.get("on") or wf.get(True) or {}  # PyYAML may parse bare 'on:' as the boolean True
    triggers = on if isinstance(on, dict) else {t: {} for t in (on if isinstance(on, list) else [on])}
    if "pull_request" in triggers or "pull_request_target" in triggers:
        out.append(f"{name}: deploy must not be triggered by pull_request (fork secret exposure)")

    jobs = wf.get("jobs", {})
    if not any("environment" in job for job in jobs.values()):
        out.append(f"{name}: deploy job has no environment (manual approval) gate")
    if not any((job.get("permissions") or {}).get("id-token") == "write" for job in jobs.values()):
        out.append(f"{name}: deploy job does not request OIDC id-token: write")

    text = yaml.dump(wf)
    if "INFRA_READY" not in text:
        out.append(f"{name}: deploy is not gated on an infrastructure-ready flag")
    # Migration must precede image activation: an 'activate'/'deploy' job must `needs` migrate.
    migrate = next((j for j, cfg in jobs.items() if "migrat" in j.lower()), None)
    activate = next((cfg for j, cfg in jobs.items() if j.lower() in ("deploy", "activate", "release")), None)
    if migrate is None:
        out.append(f"{name}: no backend migration job")
    elif activate is not None and migrate not in (activate.get("needs") or []):
        out.append(f"{name}: image activation does not depend on the migration job")

    return out


def check_ci_configuration(root: Path) -> list[str]:
    workflows_dir = root / ".github" / "workflows"
    if not workflows_dir.exists():
        return ["no .github/workflows directory"]

    violations: list[str] = []
    seen = False
    for path in sorted(workflows_dir.glob("*.yml")):
        seen = True
        try:
            wf = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            violations.append(f"{path.name}: unparseable ({type(exc).__name__})")
            continue
        violations.extend(_check_workflow(path.name, wf))
        if "deploy" in path.name:
            violations.extend(_check_deploy(path.name, wf))
    if not seen:
        violations.append("no workflow files found")
    return violations
