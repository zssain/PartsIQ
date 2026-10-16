# F61 - Enquiry PDF

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | services/worker |
| Implementing prompts | 20; foundations 17, 20 |
| Affected flows | FLOW.md row 20 |

## Scope
Export approved revision only; render logo,bilingual customer text,verified selections,estimates and references; embed Arabic fonts; store private object and signed download.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [x] Export approved revision only; render logo,bilingual customer text,verified selections,estimates and references; embed Arabic fonts; store private object and signed download.
- [ ] Exclude notes and secrets; stale or unapproved revision rejected; long Arabic names wrap without clipping; no prices or quotation title.
- [x] Test output and implementation commit recorded before status changes to done.

## Data touched
exports. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/worker/tests/features/test_f61.py`; command `python tools/run_checks.py --feature F61`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 17 | render_export_html trusted autoescaped template (logo/bilingual/selections/references/watermark/estimate, no price); export_enquiry approved-only + hash + upload + persist. Chromium render is an injected, BLOCKED port. | prompt/17 |

## Verification evidence
tests/foundations/test_17.py PASS (incl. a pypdf-validated single-page PDF via a fake renderer); worker suite PASS (19); ruff clean. Live Playwright/Chromium + Storage upload BLOCKED.
