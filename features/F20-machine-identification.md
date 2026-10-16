# F20 - Machine identification

| Field | Value |
|---|---|
| Status | planned |
| Owner module(s) | services/search |
| Implementing prompts | 06; foundations 02, 06 |
| Affected flows | FLOW.md row 06 |

## Scope
Preserve identify_machine logic for model, serial and rating; return resolved configuration or explicit missing/ambiguous status; normalize numeric serial only after preserving input.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Preserve identify_machine logic for model, serial and rating; return resolved configuration or explicit missing/ambiguous status; normalize numeric serial only after preserving input.
- [ ] Boundary serials match exactly one configuration; overlapping ranges fail database insertion; conflicting hints never silently override.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
equipment_models, model_configurations. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/search/tests/features/test_f20.py`; command `python tools/run_checks.py --feature F20`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 06 | identify_machine characterized + boundary-serial/mismatch/conflicting-hint cases in services/search/tests/features/test_f20.py. Live DB/BGE-M3 BLOCKED. | prompt/06 |
| 2026-10-17 | 02 | Schema migration applied verbatim: serial-range EXCLUDE gist guarantees exactly-one configuration per serial; model_code trigram index preserved. Verified structurally in test_02.py. Runtime identify_machine owned by prompt 06. | prompt/02 |

## Verification evidence
Build-kit coverage verified by tools/kit/verify_kit.py. Application tests have not run because this deliverable is an implementation kit. Do not report this feature as implemented until its owning prompt executes.
