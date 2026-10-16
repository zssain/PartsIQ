# F45 - Reply drafting

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | services/orchestrator |
| Implementing prompts | 13; foundations 13 |
| Affected flows | FLOW.md row 13 |

## Scope
Generate greeting,explanation and closing as structured slots; code inserts all numbers and allocations; choose Arabic or English from confirmed preference.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [x] Generate greeting,explanation and closing as structured slots; code inserts all numbers and allocations; choose Arabic or English from confirmed preference.
- [x] Unapproved critical facts never rendered; unsupported slots rejected; provider failure permits staff-authored controlled draft.
- [x] Test output and implementation commit recorded before status changes to done.

## Data touched
drafts. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/orchestrator/tests/features/test_f45.py`; command `python tools/run_checks.py --feature F45`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 13 | draft_reply structured slots + validate_slots prose guard; render_reply code-owned escaped layout; staff-authored fallback on provider failure. | prompt/13 |

## Verification evidence
services/orchestrator/tests/features/test_f45.py PASS under the orchestrator suite (28 passed, 1 skipped) and tests/foundations/test_13.py (16); run_checks --prompt 13 exits 0; ruff clean. Live OpenAI and the live drafts adapter remain BLOCKED (fake client + in-memory store).
