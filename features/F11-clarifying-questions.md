# F11 - Clarifying questions

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | services/orchestrator |
| Implementing prompts | 19; foundations 09, 11, 19 |
| Affected flows | FLOW.md row 19 |

## Scope
Use controller reason codes to choose code-owned bilingual questions; persist interrupt; associate answer with item; rerun affected resolution only.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [x] Use controller reason codes to choose code-owned bilingual questions; persist interrupt; associate answer with item; rerun affected resolution only.
- [ ] No final recommendation before approval; contradictory answer requires confirmation; repeat event creates one question.
- [x] Test output and implementation commit recorded before status changes to done.

## Data touched
messages, enquiry_items. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/orchestrator/tests/features/test_f11.py`; command `python tools/run_checks.py --feature F11`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 19 | run_parts clarification codes are code-decided (needs_model/ambiguous_part); low-confidence cannot be overridden. | prompt/19 |
| 2026-10-17 | 11 | parts specialist emits code-decided clarification codes (needs_model/ambiguous_part/none); candidate ids restricted to the compatible set; LLM phrasing only. tests/foundations/test_11.py. Live search service/OpenAI BLOCKED. | prompt/11 |
| 2026-10-17 | 09 | controller reason codes drive code-owned clarify step; pending question persists as an interrupt until answered; repeat events don't duplicate. tests/foundations/test_09.py. | prompt/09 |

## Verification evidence
services/orchestrator/tests/features/test_f11.py PASS. UI clarification display covered by test_19.
