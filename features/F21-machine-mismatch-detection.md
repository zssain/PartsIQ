# F21 - Machine mismatch detection

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | services/search |
| Implementing prompts | 06; foundations 06 |
| Affected flows | FLOW.md row 06 |

## Scope
Compare model and serial together; return mismatch reason with safe next question; prevent retrieval while identity unresolved.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Compare model and serial together; return mismatch reason with safe next question; prevent retrieval while identity unresolved.
- [ ] Valid serial of a different model does not match requested model; nonnumeric serial handled without crashing.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
model_configurations. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/search/tests/features/test_f21.py`; command `python tools/run_checks.py --feature F21`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 06 | implemented by prompt 06 (prior session); trace flipped to done after re-running its test | committed on prompt/12-deterministic-verification |
| 2026-10-17 | 06 | model+serial compared together; nonnumeric serial safe; retrieval blocked until resolved. test_f21.py. Live DB/BGE-M3 BLOCKED. | prompt/06 |

## Verification evidence
Application implemented by prompt 06; its acceptance test services/search/tests/features/test_f21.py re-verified passing in the owning service suite this session (search 88 / orchestrator 87+1skip / gateway 141 overall). ruff clean. Live infrastructure for the owning service remains BLOCKED and offline-faked per that prompt's notes.
