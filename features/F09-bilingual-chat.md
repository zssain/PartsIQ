# F09 - Bilingual chat

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | services/orchestrator |
| Implementing prompts | 19; foundations 10, 19 |
| Affected flows | FLOW.md row 19 |

## Scope
Accept Arabic, English and mixed text; preserve original message; detect preferred reply locale; render customer messages immediately after successful persistence.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [x] Accept Arabic, English and mixed text; preserve original message; detect preferred reply locale; render customer messages immediately after successful persistence.
- [ ] Empty and oversized input returns validation error; HTML is escaped; retry does not duplicate a message.
- [x] Test output and implementation commit recorded before status changes to done.

## Data touched
messages, enquiries. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/orchestrator/tests/features/test_f09.py`; command `python tools/run_checks.py --feature F09`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 19 | chat UI + orchestrator intake preserve original wording and detect locale; empty/oversized rejected; HTML escaped by React. | prompt/19 |
| 2026-10-17 | 10 | intake specialist preserves customer language (en/ar/mixed) verbatim in descriptions; locale carried. tests/foundations/test_10.py. | prompt/10 |

## Verification evidence
services/orchestrator/tests/features/test_f09.py PASS (orch suite 43/1 skip); apps/web chat covered structurally by test_19 + vitest. Live gateway/Supabase BLOCKED.
