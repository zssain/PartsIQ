# F16 - Photo quality feedback

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | services/worker |
| Implementing prompts | F16; foundations 16, 19 |
| Affected flows | FLOW.md row F16 |

## Scope
Check decodability, dimensions and blur heuristic before paid call; return actionable retake instructions; mark heuristic as advisory; allow a readable image despite noncritical blur warning.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Check decodability, dimensions and blur heuristic before paid call; return actionable retake instructions; mark heuristic as advisory; allow a readable image despite noncritical blur warning.
- [ ] Unsupported format rejected; dark or low-resolution sample gets guidance; no fabricated OCR confidence percentage.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
extractions. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/worker/tests/features/test_f16.py`; command `python tools/run_checks.py --feature F16`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | F16 | assess_photo pre-check + dispatcher gate + web PhotoQualityNotice/lib; wired into Chat + landing | committed on prompt/12-deterministic-verification |

## Verification evidence
Build-kit coverage verified by tools/kit/verify_kit.py. Application now implemented: worker suite 33 passed incl. services/worker/tests/features/test_f16.py (11 cases: good image readable+no issues, unsupported/undecodable/format-mismatch rejected, low-res/dark guidance, blur advisory, no confidence %, bomb rejected, dispatcher gate). ruff clean; apps/web vitest 20 passed. ESLint blocked in this env (missing @eslint/eslintrc). Live Storage fetch and the nameplate paid-path invocation remain BLOCKED.
