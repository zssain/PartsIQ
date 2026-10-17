# F69 - Demo walkthrough

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | docs |
| Implementing prompts | F69; foundations 27 |
| Affected flows | FLOW.md row F69 |

## Scope
Create 3-minute and 8-minute scripts covering happy path,missing serial,incompatibility,stock split and human review; include recording checklist and captions.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Create 3-minute and 8-minute scripts covering happy path,missing serial,incompatibility,stock split and human review; include recording checklist and captions.
- [ ] Do not claim video exists until recorded; use synthetic data; show failure handling and reset; verify links before sending recruiters.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
none. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`tests/acceptance/test_f69.py`; command `python tools/run_checks.py --feature F69`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | F69 | docs/DEMO_SCRIPT.md (3+8 min scripts, 5 scenarios, captions) + docs/RECORDING_CHECKLIST.md | committed on prompt/12-deterministic-verification |

## Verification evidence
Application implemented: run_checks --feature F69 -> tests/acceptance/test_f69.py PASS (7 cases incl. no-false-video-claim). ruff clean.
