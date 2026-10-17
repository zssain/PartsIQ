# F10 - Structured extraction

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | services/orchestrator |
| Implementing prompts | 10; foundations 09, 10 |
| Affected flows | FLOW.md row 10 |

## Scope
Extract item descriptions, quantities, urgency and machine hints with strict structured outputs; preserve source spans; missing quantity becomes a clarification rather than assumed order quantity.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Extract item descriptions, quantities, urgency and machine hints with strict structured outputs; preserve source spans; missing quantity becomes a clarification rather than assumed order quantity.
- [ ] Unknown keys and invalid quantities reject the response; unsupported model output cannot progress to search.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
enquiry_items, enquiries. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/orchestrator/tests/features/test_f10.py`; command `python tools/run_checks.py --feature F10`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 10 | implemented by prompt 10 (prior session); trace flipped to done after re-running its test | committed on prompt/12-deterministic-verification |
| 2026-10-17 | 10 | strict IntakeResult structured output via shared wrapper; source spans; missing quantity stays null (clarification, not assumed); disallowed fields/invalid quantity rejected; confirmed machine not overwritten. test_10.py + services/orchestrator/tests/features/test_f10.py. Live OpenAI BLOCKED. | prompt/10 |

## Verification evidence
Application implemented by prompt 10; its acceptance test services/orchestrator/tests/features/test_f10.py re-verified passing in the owning service suite this session (search 88 / orchestrator 87+1skip / gateway 141 overall). ruff clean. Live infrastructure for the owning service remains BLOCKED and offline-faked per that prompt's notes.
