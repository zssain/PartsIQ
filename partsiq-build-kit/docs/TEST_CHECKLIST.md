# Test strategy and acceptance gates

## Specification checks versus application tests

The kit validator checks references, schemas, prompt coverage and archive structure. It does not prove that the application works. The implementation agent must execute every named test as source is built. Never mark live Snowflake, OpenAI, RLS or hosted acceptance passed using mocks.

## Test layers

Unit tests cover Arabic normalization, serial boundaries, fitment filtering, supersession cycles, rank margins, allocation bounds, fact hashes, fixed transitions and redaction. Integration tests use real disposable PostgreSQL constraints, RLS, actor context reset, Storage policies, idempotency, approval races, job leases and catalogue activation. Contract tests compare the 77 REST operations, strict fields, Problem responses and frontend types.

Each of the 69 features has backend and frontend acceptance paths. Browser tests cover both languages, RTL, keyboard navigation, 360px layouts, themes, long content and four demos. Provider checks separately exercise Snowflake key-pair login, round-trip hashes and duplicate validation, plus OpenAI structured text/vision and allowance accounting. Hosted checks cover CORS, TLS, private ports, worker restart and observed latency.

## Required failure cases

| Failure | Required behavior |
|---|---|
| Exact part number is incompatible | Exclude before ranking |
| Two candidates have close scores | Ask a question or require staff selection |
| OCR identifiers are unconfirmed | Do not resolve the machine |
| Quantity changes during processing | Discard old lease output |
| Two approvals race | Publish once for the current revision |
| Stock changes before approval | Return 409 and require replanning/review |
| Source version has duplicate keys | Do not activate |
| Remote upload succeeds but local commit fails | Keep old version active |
| Reporting acknowledgement is lost | Replay the same event ID without duplication |
| Redis is unavailable | Deny rate-limited intake; retain durable jobs |
| Provider completion is uncertain | Hold the usage reservation |
| Free allowance expires | Block live work; no paid fallback |
| Demo is reset during a job | Reject old-generation writes |
| Reviewer assignment changes | Remove previous reviewer access |
| Instructions are injected into text/photo | No privileged action occurs |

## Evidence and final gate

For every check, record command, environment, commit, time, expected result, actual result and sanitized logs. Accuracy requires a denominator; latency requires hardware and runtime context. A skip is not a pass. A resolver result is not a runtime build, and SQL parsing is not live policy validation. Do not remove required tests to obtain a green result.

During incremental development, CI validates completed prompt owners and requires that their named tests exist. The final release gate requires every feature, all 77 operations, and all mandatory tests. Live checks lacking account access remain visibly blocked; they cannot be replaced with fixture evidence.
