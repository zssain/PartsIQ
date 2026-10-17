# F65 - Correction feedback

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | services/gateway |
| Implementing prompts | F65; foundations 14, 21, 23 |
| Affected flows | FLOW.md row F65 |

## Scope
List authorized before/after corrections; let admin curate anonymized labelled eval cases; record reviewer and source revision; never auto-train on unreviewed edits.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] List authorized before/after corrections; let admin curate anonymized labelled eval cases; record reviewer and source revision; never auto-train on unreviewed edits.
- [ ] Private text excluded from exported fixtures; duplicate case source detected; unreviewed correction cannot become ground truth.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
correction_records, eval_cases. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/gateway/tests/features/test_f65.py`; command `python tools/run_checks.py --feature F65`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | F65 | curate_correction + list_corrections + POST /v1/staff/corrections/{id}/eval-case + web CorrectionFeedback | committed on prompt/12-deterministic-verification |

## Verification evidence
Application implemented: gateway suite 141 passed incl. services/gateway/tests/features/test_f65.py (10 cases). ruff clean; apps/web vitest 44. Live corrections/eval-case adapter BLOCKED.
