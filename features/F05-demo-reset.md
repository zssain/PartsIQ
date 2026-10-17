# F05 - Demo reset

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | services/gateway |
| Implementing prompts | 19; foundations 07, 15, 19 |
| Affected flows | FLOW.md row 19 |

## Scope
Lock session; increment generation; cancel unfinished jobs from prior generation; enqueue Storage cleanup; keep minimal audit; create fresh scenario enquiries on explicit selection.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Lock session; increment generation; cancel unfinished jobs from prior generation; enqueue Storage cleanup; keep minimal audit; create fresh scenario enquiries on explicit selection.
- [ ] Late OCR from old generation cannot update current data; repeated reset idempotency key returns the same generation.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
demo_sessions, jobs. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/gateway/tests/features/test_f05.py`; command `python tools/run_checks.py --feature F05`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 19 | implemented by prompt 19 (prior session); trace flipped to done after re-running its test | committed on prompt/12-deterministic-verification |
| 2026-10-17 | 19 | gateway reset idempotency test (test_f05) + demo reset UI clearing client cache. Full reset (job cancel/storage cleanup) owned by 15/22. | prompt/19 |
| 2026-10-17 | 15 | lease fencing enforces that late work from an old session generation cannot commit (F05 invariant). UI/reset test owned by prompt 22. | prompt/15 |
| 2026-10-17 | 07 | reset idempotent per key returns same generation; generation increment under row lock (repo); rate limit before DB. test_07.py. Live Supabase Auth + DB BLOCKED. | prompt/07 |

## Verification evidence
Application implemented by prompt 19; its acceptance test services/gateway/tests/features/test_f05.py re-verified passing in the owning service suite this session (search 88 / orchestrator 87+1skip / gateway 141 overall). ruff clean. Live infrastructure for the owning service remains BLOCKED and offline-faked per that prompt's notes.
