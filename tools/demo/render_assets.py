"""Generate the demo fixtures: scenarios, nameplate images, cited evidence + manifests.

Deterministic build step. It regenerates the seed-42 catalogue, derives the four
scenarios, renders a synthetic nameplate PNG and a cited evidence PDF, and writes hash
manifests. If validate_scenarios reports ANY problem it FAILS (non-zero exit) rather
than emit an undemonstrable demo (F02). It performs no database or provider I/O.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = REPO_ROOT / "tools" / "demo"
sys.path.insert(0, str(DEMO_DIR))
sys.path.insert(0, str(REPO_ROOT / "tools" / "catalog"))

import build_scenarios as bs  # noqa: E402

from catalog.generator import generate_catalog  # noqa: E402

NAMEPLATES = DEMO_DIR / "nameplates"
EVIDENCE = DEMO_DIR / "catalogue_evidence"
SCENARIO_DIR = DEMO_DIR / "scenarios"
SEED = 42


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest_entry(path: Path) -> dict:
    return {"file": path.name, "sha256": _sha256(path), "bytes": path.stat().st_size}


def _render_evidence_pdf(source_reference: str, destination: Path) -> None:
    """Render a one-page cited evidence PDF (synthetic)."""
    from PIL import Image, ImageDraw

    destination.parent.mkdir(parents=True, exist_ok=True)
    page = Image.new("RGB", (612, 792), color=(255, 255, 255))  # US Letter @ 72dpi
    draw = ImageDraw.Draw(page)
    draw.text((56, 56), "PartsIQ synthetic catalogue evidence", fill=(0, 0, 0))
    draw.text((56, 96), f"Source reference: {source_reference}", fill=(0, 0, 0))
    draw.text((56, 136), "All part numbers are fictional synthetic data.", fill=(0, 0, 0))
    page.save(destination, format="PDF")


def main() -> int:
    dataset = generate_catalog(SEED)
    scenarios = bs.build_scenarios(dataset)

    errors = bs.validate_scenarios(scenarios, dataset)
    if errors:
        for error in errors:
            print(f"scenario validation error: {error}", file=sys.stderr)
        print(f"FAILED: {len(errors)} scenario validation error(s); refusing to emit demo fixtures.", file=sys.stderr)
        return 1

    # Per-scenario + combined JSON.
    SCENARIO_DIR.mkdir(parents=True, exist_ok=True)
    for scenario in scenarios:
        (SCENARIO_DIR / f"{scenario.id}.json").write_text(
            json.dumps(scenario.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8"
        )
    (DEMO_DIR / "scenarios.json").write_text(
        json.dumps([s.model_dump(mode="json") for s in scenarios], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Nameplate image for the photo scenario.
    photo = next(s for s in scenarios if s.id == "mixed_photo")
    assert photo.attachment_path is not None
    nameplate_path = REPO_ROOT / photo.attachment_path
    model_label = photo.attachment_path.rsplit("/", 1)[-1].removesuffix(".png")
    bs.render_nameplate(model_label, model_label.rsplit("_", 1)[-1], nameplate_path)

    # Cited evidence PDF for the first compatibility source reference.
    first_compat = sorted(
        dataset.compatibility, key=lambda c: (c.brand, c.model_code, c.config_code, c.part_number)
    )[0]
    evidence_path = EVIDENCE / f"{first_compat.source_reference.replace(' ', '_').replace(',', '')}.pdf"
    _render_evidence_pdf(first_compat.source_reference, evidence_path)

    # Hash manifests.
    NAMEPLATES.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (NAMEPLATES / "manifest.json").write_text(
        json.dumps({"seed": SEED, "assets": [_manifest_entry(nameplate_path)]}, indent=2), encoding="utf-8"
    )
    (EVIDENCE / "manifest.json").write_text(
        json.dumps({"seed": SEED, "assets": [_manifest_entry(evidence_path)]}, indent=2), encoding="utf-8"
    )
    print(f"generated {len(scenarios)} scenarios, 1 nameplate, 1 evidence page (seed {SEED}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
