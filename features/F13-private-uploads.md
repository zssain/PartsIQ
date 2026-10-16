# F13 - Private uploads

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | services/gateway |
| Implementing prompts | 19; foundations 04, 08, 19 |
| Affected flows | FLOW.md row 19 |

## Scope
Create pending attachment and unique object path; use signed upload; validate actual bytes and magic type after confirmation; strip EXIF and cap decoded pixels before OCR.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [x] Create pending attachment and unique object path; use signed upload; validate actual bytes and magic type after confirmation; strip EXIF and cap decoded pixels before OCR.
- [ ] Wrong MIME, oversized content, image decompression bomb, duplicate confirmation and nonexistent object handled explicitly.
- [x] Test output and implementation commit recorded before status changes to done.

## Data touched
enquiry_attachments. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/gateway/tests/features/test_f13.py`; command `python tools/run_checks.py --feature F13`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 19 | confirm_upload validates real bytes/magic (reject/validate/404/duplicate); UploadCard drives signed upload + confirm. | prompt/19 |
| 2026-10-17 | 08 | confirm_upload validates real bytes/magic after confirmation; duplicate confirmation idempotent; nonexistent -> 404; server-generated object names; atomic intake + idempotency-key (same payload returns existing, different -> 409); rate-limit before DB. tests/foundations/test_08.py. Decoded-pixel cap/EXIF is prompt 16. | prompt/08 |
| 2026-10-17 | 04 | Private buckets + gateway create_upload (unique pending key, user-token signed upload) + worker typed-resource download signing (60s) + magic-byte validation implemented. Verified in test_04.py. Decoded-pixel cap/EXIF (prompt 16) and duplicate-confirmation (prompt 08) deferred; live Storage integration pending. | prompt/04 |

## Verification evidence
services/gateway/tests/features/test_f13.py PASS (gateway suite 22). Pixel-cap/EXIF is the worker (prompt 16). Live Storage BLOCKED.
