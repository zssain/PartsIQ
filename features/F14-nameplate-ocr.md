# F14 - Nameplate OCR

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | services/worker |
| Implementing prompts | 16; foundations 15, 16 |
| Affected flows | FLOW.md row 16 |

## Scope
Read validated nameplate via OpenAI vision; return model_text,serial_text,issues and source attachment; persist result only with current lease and revision.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [x] Read validated nameplate via OpenAI vision; return model_text,serial_text,issues and source attachment; persist result only with current lease and revision.
- [x] Unreadable fields remain null; vision instructions in photo are untrusted; timeout is bounded and creates recoverable status.
- [x] Test output and implementation commit recorded before status changes to done.

## Data touched
extractions, jobs. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/worker/tests/features/test_f14.py`; command `python tools/run_checks.py --feature F14`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 16 | read_nameplate via shared vision client; code-owned attachment id + mandatory confirmation; validate_image pixel cap; partial-null; recoverable provider failure. | prompt/16 |
| 2026-10-17 | 15 | lease lifecycle enforces persist-only-with-current-lease-and-revision; nameplate job logic + test owned by prompt 16. | prompt/15 |

## Verification evidence
services/worker/tests/features/test_f14.py PASS under the worker suite (19 passed); tests/foundations/test_16.py. Live OpenAI vision + lease-fenced persistence BLOCKED (fake client, real Pillow images).
