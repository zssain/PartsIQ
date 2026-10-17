# F58 - Catalogue imports

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | services/worker |
| Implementing prompts | F58; foundations 02, 05, 15 |
| Affected flows | FLOW.md row F58 |

## Scope
Read CSV UTF-8 or XLSX without evaluating formulas; validate row schema,references,serial overlap,supersession cycles and source evidence; show dry-run report; explicit admin publish.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Read CSV UTF-8 or XLSX without evaluating formulas; validate row schema,references,serial overlap,supersession cycles and source evidence; show dry-run report; explicit admin publish.
- [ ] Invalid batch changes no published data; file with macros/formulas rejected; 50000-row and 10MiB limits enforced; public demo cannot publish.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
import_batches, import_rows. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/worker/tests/features/test_f58.py`; command `python tools/run_checks.py --feature F58`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | F58 | validate_import dry-run (CSV/XLSX, no formula eval, macro/limit/schema checks) + dispatcher + gateway routes + web ImportWizard | committed on prompt/12-deterministic-verification |

## Verification evidence
Application implemented: worker suite 48 passed incl. services/worker/tests/features/test_f58.py (15 cases). gateway 71; ruff clean; apps/web vitest 20. openpyxl==3.1.5 pinned (uv.lock additive). Live import store + worker execution BLOCKED.
