"""Approved-snapshot HTML renderer for the bilingual PDF export (prompt 17 — F61).

Ported and consolidated from the legacy worker ``services/worker/app/jobs/export_pdf.py``
(``render_export_html``) and its Jinja template onto the single ``partsiq`` package.

Contract:
    def render_export_html(snapshot: ApprovedSnapshot) -> str

The function fills a TRUSTED, code-owned Jinja template with autoescape ON. Every interpolated
value — the part identifiers, part names and source references drawn from the verified facts —
is HTML-escaped by Jinja. The ONLY value marked ``|safe`` is ``snapshot.reply``, which the
code-owned reply renderer (``partsiq.enquiries.renderer``, prompt 13) already produced as
HTML-escaped markup. No model-authored string is ever evaluated as a template, so injected
catalogue or customer text cannot execute as markup inside the PDF (CONSTRAINTS rule 10, F27).

Arabic renders right-to-left (``dir="rtl"`` + Arabic fonts); identifiers stay LTR-isolated and
long mixed Arabic/English names wrap rather than clip. The synthetic-demo watermark and the
non-guaranteed-estimate note are always present; no price/quotation wording and no staff note
or secret is ever emitted (CONSTRAINTS rules 1, 14; F61).

This function performs no network or database I/O beyond reading the bundled template file.
The HTML→PDF step itself (Chromium via Playwright) is a separate, injected port in
``service.py``; the live browser is BLOCKED in this environment.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from partsiq.core.contracts import ApprovedSnapshot

# The trusted template lives beside this module (code-owned, prompt 17).
_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_TEMPLATE_NAME = "enquiry.html"

# Bundled licensed brand assets (logo + Noto Latin/Arabic fonts) shipped with the web app.
# Chromium reads only these local files when it renders; the HTML never fetches the network.
_ASSET_DIR = (
    Path(__file__).resolve().parents[3] / "web" / "public" / "brand"
)


@lru_cache(maxsize=1)
def _env() -> Environment:
    """Build the Jinja environment once. Autoescape is ON for HTML (defence in depth)."""
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"], default_for_string=True),
    )


def render_export_html(snapshot: ApprovedSnapshot, *, asset_dir: Path | str | None = None) -> str:
    """Render the trusted export template from an approved snapshot.

    ``asset_dir`` overrides the bundled brand-asset location (tests may point it anywhere);
    it is never derived from untrusted input. The rendered string is deterministic for a
    given snapshot and asset directory.
    """
    template = _env().get_template(_TEMPLATE_NAME)
    assets = Path(asset_dir) if asset_dir is not None else _ASSET_DIR
    return template.render(
        locale=snapshot.locale,
        facts=snapshot.facts,
        reply=snapshot.reply,
        synthetic=snapshot.synthetic,
        asset_dir=str(assets),
    )


__all__ = ["render_export_html"]
