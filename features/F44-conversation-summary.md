# F44 - Conversation summary

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | services/orchestrator |
| Implementing prompts | F44; foundations 09, 13, 20 |
| Affected flows | FLOW.md row F44 |

## Scope
Produce staff-only concise summary from authorized messages and confirmed fields; store message IDs and revision; use shared budget wrapper; regenerate on relevant change.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Produce staff-only concise summary from authorized messages and confirmed fields; store message IDs and revision; use shared budget wrapper; regenerate on relevant change.
- [ ] Outdated summary labelled stale; instructions inside messages ignored; exhausted budget leaves full conversation available.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
enquiry_summaries. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/orchestrator/tests/features/test_f44.py`; command `python tools/run_checks.py --feature F44`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | F44 | summarize_enquiry (budget-gated, code-owned ids) + /internal/enquiries/summary + gateway route + web ConversationSummary | committed on prompt/12-deterministic-verification |

## Verification evidence
Application implemented: orchestrator 73+1skip incl. services/orchestrator/tests/features/test_f44.py (6 cases). gateway 115; ruff clean; apps/web vitest 29. Live OpenAI summary + store BLOCKED.
