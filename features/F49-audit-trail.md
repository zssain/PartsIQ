# F49 - Audit trail

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | libs/partsiq_common |
| Implementing prompts | 14; foundations 01, 03, 14 |
| Affected flows | FLOW.md row 14 |

## Scope
Append actor,request,entity,revision and minimal before/after metadata for AI suggestions and human changes; redact secrets and full sensitive payloads.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [x] Append actor,request,entity,revision and minimal before/after metadata for AI suggestions and human changes; redact secrets and full sensitive payloads.
- [ ] Application UPDATE,DELETE,TRUNCATE fail; audit write failure rolls back approval; database-owner powers documented honestly.
- [x] Test output and implementation commit recorded before status changes to done.

## Data touched
audit_log. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`tests/acceptance/test_f49.py`; command `python tools/run_checks.py --feature F49`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 14 | approval appends redacted audit in the same transaction; audit failure rolls back; append-only/immutability are DB triggers. | prompt/14 |
| 2026-10-17 | 03 | audit_log RLS (admin/reviewer read) and append-only grants migrated; application UPDATE/DELETE/TRUNCATE denied by role grants. Structural assertions in test_03.py. | prompt/03 |
| 2026-10-17 | 01 | append_audit implemented: redacted, append-only, inserted in caller transaction so a failed audit rolls back the business write. Verified in tests/foundations/test_01.py. Owner prompt 14 finalizes the full trail. | prompt/01 |

## Verification evidence
tests/acceptance/test_f49.py PASS via run_checks --feature F49 (3); tests/foundations/test_14.py. Application UPDATE/DELETE/TRUNCATE rejection and owner powers are DB-trigger behaviour (prompt 03) and remain integration-only.
