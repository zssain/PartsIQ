# F38 - Correct extracted details

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | services/orchestrator |
| Implementing prompts | F38; foundations 09, 14, 20 |
| Affected flows | FLOW.md row F38 |

## Scope
Lock enquiry; compare expected revision; apply typed allowed corrections; increment revision; invalidate derived selections/draft/approval; enqueue recomputation; record before and after.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Lock enquiry; compare expected revision; apply typed allowed corrections; increment revision; invalidate derived selections/draft/approval; enqueue recomputation; record before and after.
- [ ] Unknown field rejected; old revision returns 409; correction cannot directly set approved status or invent candidate facts.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
enquiry_revisions, correction_records. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/orchestrator/tests/features/test_f38.py`; command `python tools/run_checks.py --feature F38`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | F38 | correct_extraction over revise + reset_derived_state + /internal/enquiries/correct + gateway route + web CorrectionEditor | committed on prompt/12-deterministic-verification |

## Verification evidence
Application implemented: orchestrator 67+1skip incl. services/orchestrator/tests/features/test_f38.py (8 cases). gateway 87; ruff clean; apps/web vitest 29. Live locked revision tx + forward BLOCKED.
