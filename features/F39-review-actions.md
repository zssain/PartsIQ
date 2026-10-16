# F39 - Review actions

| Field | Value |
|---|---|
| Status | planned |
| Owner module(s) | services/orchestrator |
| Implementing prompts | 20; foundations 14, 20 |
| Affected flows | FLOW.md row 20 |

## Scope
Approve only verified current draft; edit prose through controlled schema then reverify; reject with reason; record actor and idempotency key.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Approve only verified current draft; edit prose through controlled schema then reverify; reject with reason; record actor and idempotency key.
- [ ] Double-click publishes once; concurrent edit defeats stale approval; failed verification blocks publication.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
review_decisions. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/orchestrator/tests/features/test_f39.py`; command `python tools/run_checks.py --feature F39`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |

## Verification evidence
Build-kit coverage verified by tools/kit/verify_kit.py. Application tests have not run because this deliverable is an implementation kit. Do not report this feature as implemented until its owning prompt executes.
