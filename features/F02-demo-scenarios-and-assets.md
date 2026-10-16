# F02 - Demo scenarios and assets

| Field | Value |
|---|---|
| Status | planned |
| Owner module(s) | tools/catalog |
| Implementing prompts | 19; foundations 05, 19 |
| Affected flows | FLOW.md row 19 |

## Scope
Seed four deterministic scenarios: mixed-language photo, missing serial, incompatible part, local shortage; derive identifiers from seed 42; validate expected outcomes against generated records.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Seed four deterministic scenarios: mixed-language photo, missing serial, incompatible part, local shortage; derive identifiers from seed 42; validate expected outcomes against generated records.
- [ ] Reject a scenario whose expected part lacks compatibility; reject stock claims not supported by fixture quantities.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
demo_sessions, enquiries. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`tests/acceptance/test_f02.py`; command `python tools/run_checks.py --feature F02`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 05 | Four deterministic scenarios (mixed_photo, missing_serial, incompatible_number, local_shortage) derived from real seed-42 records; nameplate PNG + cited evidence PDF + hash manifests generated; validate_scenarios rejects incompatible expected parts and unsupported stock claims. Verified in test_05.py. Base DB load + role-gated seed transaction BLOCKED (no Postgres). | prompt/05 |

## Verification evidence
Build-kit coverage verified by tools/kit/verify_kit.py. Application tests have not run because this deliverable is an implementation kit. Do not report this feature as implemented until its owning prompt executes.
