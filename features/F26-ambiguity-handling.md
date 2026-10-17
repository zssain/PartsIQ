# F26 - Ambiguity handling

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | services/orchestrator |
| Implementing prompts | 11; foundations 06, 11 |
| Affected flows | FLOW.md row 11 |

## Scope
Use tested score and margin thresholds in code; ask customer to distinguish fuel filter versus separator; allow staff to select only verified candidates.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Use tested score and margin thresholds in code; ask customer to distinguish fuel filter versus separator; allow staff to select only verified candidates.
- [ ] LLM cannot override low confidence; unavailable candidate choice returns 409; thresholds evaluated on labelled cases.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
enquiry_items. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/orchestrator/tests/features/test_f26.py`; command `python tools/run_checks.py --feature F26`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 11 | implemented by prompt 11 (prior session); trace flipped to done after re-running its test | committed on prompt/12-deterministic-verification |
| 2026-10-17 | 11 | tested score/margin thresholds in code decide ambiguous_part; LLM cannot override low confidence; unavailable candidate choice returns 409; tool calls bounded (4); stale catalogue rejected. test_11.py + services/orchestrator/tests/features/test_f26.py. Live search service/OpenAI BLOCKED. | prompt/11 |

## Verification evidence
Application implemented by prompt 11; its acceptance test services/orchestrator/tests/features/test_f26.py re-verified passing in the owning service suite this session (search 88 / orchestrator 87+1skip / gateway 141 overall). ruff clean. Live infrastructure for the owning service remains BLOCKED and offline-faked per that prompt's notes.
