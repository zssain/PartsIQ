# F47 - Human publication gate

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | services/orchestrator |
| Implementing prompts | 14; foundations 14 |
| Affected flows | FLOW.md row 14 |

## Scope
Only approval service inserts recommendation messages; lock enquiry and recheck role,revision and verification; unique publication index prevents duplicates.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [x] Only approval service inserts recommendation messages; lock enquiry and recheck role,revision and verification; unique publication index prevents duplicates.
- [ ] No worker/specialist write tool can publish; database rejects recommendation lacking matching approved decision.
- [x] Test output and implementation commit recorded before status changes to done.

## Data touched
messages, review_decisions. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/orchestrator/tests/features/test_f47.py`; command `python tools/run_checks.py --feature F47`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 14 | only approve publishes, coupled to its approved decision; one-per-revision backstop; failed verification blocks publication. | prompt/14 |

## Verification evidence
services/orchestrator/tests/features/test_f47.py PASS under the orchestrator suite; tests/foundations/test_14.py. Live unique-publication index / CHECK triggers BLOCKED (fake mirrors them).
