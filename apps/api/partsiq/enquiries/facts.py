"""Canonical fact hashing and version-specific citation resolution (prompt 12).

Two deterministic, side-effect-free helpers that the verification gate depends on:

``facts_sha256`` canonicalizes a :class:`VerifiedFacts` — object keys sorted, Decimals
rendered as decimal strings, and the item/allocation lists ordered — before SHA-256, so the
stored hash is stable and independent of the input ordering. Reordering items or allocations
yields the same hash; two facts that differ only in Decimal scale that still compare equal
are rendered the same way through pydantic's JSON mode.

``resolve_source_reference`` parses the version-specific catalogue citation (F28). The
embedded ``rev`` is what pins the document to a catalogue version; the section is the
page/anchor the evidence viewer opens. A blank citation, or one without an explicit
revision, cannot be pinned to a version and therefore does not resolve — it must flag review
rather than back an approval (F28, "missing source file blocks evidence viewer and flags
review"). No LLM is involved anywhere here.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from partsiq.core.contracts import VerifiedFacts

# The synthetic catalogue records references shaped like
#   "SYNTH-CA-PB-CA-110 rev 1, section FILTERS"
# (tools/catalog generator). The embedded revision is what makes the document
# version-specific; the section is the page/anchor the evidence viewer opens.
_SOURCE_RE = re.compile(
    r"^\s*(?P<doc>.+?)\s+rev\s+(?P<rev>\w+)\s*,\s*section\s+(?P<section>.+?)\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class Citation:
    """A resolved, version-specific source reference (F28)."""

    document: str
    page: str
    revision: str | None
    resolved: bool


def resolve_source_reference(source_reference: str) -> Citation:
    """Resolve a compatibility ``source_reference`` to a version-specific document+page.

    A blank reference, or one with no explicit revision, cannot be pinned to a catalogue
    version: it does not resolve and must flag review rather than back an approval.
    """
    if not source_reference or not source_reference.strip():
        return Citation(document="", page="", revision=None, resolved=False)
    match = _SOURCE_RE.match(source_reference)
    if match is None:
        return Citation(
            document=source_reference.strip(), page="", revision=None, resolved=False
        )
    return Citation(
        document=f"{match.group('doc').strip()} rev {match.group('rev')}",
        page=f"section {match.group('section').strip()}",
        revision=match.group("rev"),
        resolved=True,
    )


def _canonical_decimal(value: Decimal) -> str:
    """Render a Decimal in canonical, scale-independent, non-scientific form.

    ``Decimal("2")``, ``Decimal("2.0")`` and ``Decimal("2.00")`` all compare equal and must
    render to the same string, so the fact hash is stable regardless of how a quantity's
    trailing zeros were carried through the pipeline.
    """
    return format(value.normalize(), "f")


def _canonicalize(value: Any) -> Any:
    """Recursively render a Python-mode dump to JSON-safe, deterministic primitives."""
    if isinstance(value, Decimal):
        return _canonical_decimal(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {key: _canonicalize(sub) for key, sub in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonicalize(sub) for sub in value]
    return value


def _canonical_payload(facts: VerifiedFacts) -> dict:
    """Canonicalize values (Decimals normalized) with lists ordered so equal facts hash equally."""
    data = _canonicalize(facts.model_dump(mode="python"))
    data["items"] = sorted(
        (
            {
                **item,
                "allocations": sorted(
                    item["allocations"],
                    key=lambda a: (a["warehouse_id"], a["quantity"]),
                ),
            }
            for item in data["items"]
        ),
        key=lambda item: item["item_id"],
    )
    return data


def facts_sha256(facts: VerifiedFacts) -> str:
    """SHA-256 over the canonical JSON (sorted keys, normalized decimals, ordered lists)."""
    canonical = json.dumps(
        _canonical_payload(facts), sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
