# F14 - Nameplate OCR

| Field | Value |
|---|---|
| Status | planned |
| Owner module(s) | services/worker |
| Implementing prompts | 16; foundations 15, 16 |
| Affected flows | FLOW.md row 16 |

## Scope
Read validated nameplate via OpenAI vision; return model_text,serial_text,issues and source attachment; persist result only with current lease and revision.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Read validated nameplate via OpenAI vision; return model_text,serial_text,issues and source attachment; persist result only with current lease and revision.
- [ ] Unreadable fields remain null; vision instructions in photo are untrusted; timeout is bounded and creates recoverable status.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
extractions, jobs. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/worker/tests/features/test_f14.py`; command `python tools/run_checks.py --feature F14`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |

## Verification evidence
Build-kit coverage verified by tools/kit/verify_kit.py. Application tests have not run because this deliverable is an implementation kit. Do not report this feature as implemented until its owning prompt executes.
