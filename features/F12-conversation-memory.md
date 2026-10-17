# F12 - Conversation memory

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | services/orchestrator |
| Implementing prompts | 09; foundations 03, 09 |
| Affected flows | FLOW.md row 09 |

## Scope
Persist all messages and typed current state; compact context using retained structured facts; resume by enquiry/revision; never mix customer sessions.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Persist all messages and typed current state; compact context using retained structured facts; resume by enquiry/revision; never mix customer sessions.
- [ ] Restart retains unresolved questions; old revision events are ignored and audited; foreign thread ID denied.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
messages, enquiry_revisions. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/orchestrator/tests/features/test_f12.py`; command `python tools/run_checks.py --feature F12`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 09 | implemented by prompt 09 (prior session); trace flipped to done after re-running its test | committed on prompt/12-deterministic-verification |
| 2026-10-17 | 09 | typed EnquiryState persisted via checkpointer; resume by enquiry+revision thread; old-revision event obsolete; foreign thread has no state. services/orchestrator/tests/features/test_f12.py. | prompt/09 |
| 2026-10-17 | 03 | Per-item/per-revision candidate keys and enquiry_items/messages schema migrated; checkpoints schema created via extracted DDL (autocommit) + RLS/grants. Structural assertions in test_03.py. Resume/compaction owned by prompt 09. | prompt/03 |

## Verification evidence
Application implemented by prompt 09; its acceptance test services/orchestrator/tests/features/test_f12.py re-verified passing in the owning service suite this session (search 88 / orchestrator 87+1skip / gateway 141 overall). ruff clean. Live infrastructure for the owning service remains BLOCKED and offline-faked per that prompt's notes.
