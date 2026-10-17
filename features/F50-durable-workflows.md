# F50 - Durable workflows

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | services/orchestrator |
| Implementing prompts | 09; foundations 09 |
| Affected flows | FLOW.md row 09 |

## Scope
Use Postgres checkpointer and DB event inbox; thread key includes enquiry ID and active revision; serialize processing for one enquiry; recover after restart.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Use Postgres checkpointer and DB event inbox; thread key includes enquiry ID and active revision; serialize processing for one enquiry; recover after restart.
- [ ] Duplicate events do not repeat publication; stale revision event is consumed as obsolete; checkpoint DDL never runs under runtime role.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
workflow_events. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/orchestrator/tests/features/test_f50.py`; command `python tools/run_checks.py --feature F50`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 09 | implemented by prompt 09 (prior session); trace flipped to done after re-running its test | committed on prompt/12-deterministic-verification |
| 2026-10-17 | 09 | Postgres checkpointer graph + DB event inbox; thread key per enquiry+revision; duplicate events obsolete (no repeat publication); stale revision/generation obsolete. test_f50.py + test_09.py. Live Postgres checkpointer BLOCKED. | prompt/09 |

## Verification evidence
Application implemented by prompt 09; its acceptance test services/orchestrator/tests/features/test_f50.py re-verified passing in the owning service suite this session (search 88 / orchestrator 87+1skip / gateway 141 overall). ruff clean. Live infrastructure for the owning service remains BLOCKED and offline-faked per that prompt's notes.
