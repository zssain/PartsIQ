# F15 - OCR confirmation

| Field | Value |
|---|---|
| Status | planned |
| Owner module(s) | apps/web |
| Implementing prompts | 19; foundations 16, 19 |
| Affected flows | FLOW.md row 19 |

## Scope
Show cropped or original nameplate beside extracted identifiers; require user confirm or correction; record actor and time; preserve leading zeros in serial text.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Show cropped or original nameplate beside extracted identifiers; require user confirm or correction; record actor and time; preserve leading zeros in serial text.
- [ ] Unconfirmed OCR never authorizes matching; blank corrected serial triggers missing-serial flow; stale confirmation returns 409.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
extractions, enquiry_items. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`apps/web/tests/features/f15.test.tsx`; command `python tools/run_checks.py --feature F15`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 16 | gateway confirm_extraction backend: auth-or-404, stale 409, verbatim serial (leading zeros), blank-serial missing flow (tests/foundations/test_16.py). UI test f15.test.tsx owned by prompt 19. | prompt/16 |

## Verification evidence
Build-kit coverage verified by tools/kit/verify_kit.py. Application tests have not run because this deliverable is an implementation kit. Do not report this feature as implemented until its owning prompt executes.
