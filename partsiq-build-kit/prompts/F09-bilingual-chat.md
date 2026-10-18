# F09 Bilingual chat

## GOAL
Implement the complete bilingual chat behavior in the single-workflow Snowflake edition. Accept Arabic, English and mixed text; preserve original message; detect preferred reply locale; render customer messages immediately after successful persistence.

## CONTEXT AND PREREQUISITES
The product is a bilingual spare-parts enquiry and human-review application. Snowflake stores versioned source catalogue data and redacted reporting events; Supabase supplies authentication, private files and PostgreSQL operational records. A validated PostgreSQL catalogue mirror supports compatibility checks and fast interactive reads. One FastAPI package and one background worker run the application. OpenAI extracts text/photos and writes constrained prose; ordinary Python controls all decisions. No multi-agent framework is part of this build.

This feature extends foundations00–20 and follows F08. Read docs/PRD.md for the user outcome, docs/REST_API.md for transport rules, docs/DATA_OWNERSHIP.md for persistence, docs/WORKFLOW.md for state changes, and docs/SECURITY.md for access. Read the exact models below before implementing UI assumptions. This feature belongs to `workflow` at product level but runs inside the common application; ownership does not imply a separate service or agent. Preserve the behavior of all previously completed features.

## PACKAGES AND INSTALLATION
Reuse foundation-installed packages; this feature introduces no floating dependency. Backend: FastAPI==0.135.1 with APIRouter, Depends, HTTPException and response_model; Pydantic==2.12.5 with Field and model_validate_json; asyncpg==0.31.0 with parameterized queries and explicit transactions; httpx==0.28.1 for bounded dependency calls. Tests: pytest==9.0.2 and pytest-asyncio==1.3.0. Frontend: the exact Next.js, React, Zod, next-intl, Vitest and Testing Library versions in spec/web-package.json. Run `uv pip sync spec/python-requirements.lock` and `corepack pnpm --dir apps/web install --frozen-lockfile` only if dependencies are not already synchronized. Snowflake access belongs to the catalogue/reporting adapter, not this browser feature. No extra agent library is allowed.

## FILES AND OWNERSHIP
- `apps/api/partsiq/features/f09_bilingual_chat.py`: application facade connecting this feature to foundation domain functions.
- `apps/web/src/features/f09_bilingual_chat/Panel.tsx`: accessible bilingual feature panel and its loading/error/empty states.
- `tests/features/test_f09.py`: feature acceptance tests; exercise the real public entry point with isolated fixtures.
- `apps/web/tests/features/f09.test.tsx`: feature acceptance tests; exercise the real public entry point with isolated fixtures.
- `apps/api/partsiq/api/f09_bilingual_chat.py`: FastAPI route adapter with declared authorization and response model.

Register its router in `apps/api/partsiq/api/router.py` after the new module exists. Mount the panel in CustomerShell, StaffShell or the catalogue/admin page according to the access level. Extend existing en/ar dictionaries with namespaced keys `f09`; do not duplicate whole dictionaries. Record modifications to shared files in the handover. Add no second implementation of compatibility, approval, budget accounting or Snowflake access.

## TYPED CONTRACTS
```python
async def f09_create_enquiry(actor: ActorContext, command: EnquiryCreate, idempotency_key: UUID) -> EnquiryView
async def f09_get_enquiry(actor: ActorContext, enquiry_id: UUID) -> EnquiryView
```

```python
class EnquiryCreate(Contract):
    text: str = Field(min_length=1,max_length=12000)
    locale: Locale
    destination_warehouse_id: int = Field(gt=0)
    session_id: UUID | None = None

class EnquiryView(Contract):
    id: UUID
    revision: int
    status: Literal['received','processing','needs_information','awaiting_review','approved','rejected','failed']
    messages: list[MessageView]
    item_ids: list[UUID]
    catalogue_version_id: UUID | None
    updated_at: datetime
```

Shared nested models are fully defined in spec/contracts.py and spec/api_models.py; copy their types rather than weakening them to unvalidated dictionaries. For a UI panel define `export function Panel(props: {enquiryId?: string; locale: 'en' | 'ar'; readOnly: boolean}): React.JSX.Element`. For a pure internal feature use `FeatureContext` with request_id, actor, enquiry_id, revision and `FeatureOutcome` with passed, code, details, as defined in spec/api_models.py. ReadOnly is a UI affordance; backend authorization remains mandatory. All serials and part numbers remain strings. Serialize Decimal as strings and UUID/datetime through the shared models.

## IMPLEMENTATION STEPS
1. Read the existing domain implementation and its tests. Write down the current caller and the expected persisted outcome for F09; use the canonical endpoint owner rather than adding another path.
2. Implement the facade signature above. Derive actor identity from the verified dependency, load the scoped enquiry/item when relevant, and reject a path/body ID mismatch before querying private data. A route must never accept an arbitrary actor, role, table name or Storage path from JSON.
3. Accept Arabic, English and mixed text.
4. Preserve original message.
5. Detect preferred reply locale.
6. Render customer messages immediately after successful persistence.
7. Build the response from persisted current-revision records. Avoid returning internal notes, raw provider payloads, keys or object credentials. Use response_model filtering as an additional check, not as the only authorization boundary.
8. Wire the frontend through apiFetch and the exact response schema. Implement loading, empty, success, validation error, stale revision, forbidden and dependency-unavailable states where they apply. Disable duplicate submit while pending and keep a stable idempotency key for an explicit retry of the same operation.
9. Re-fetch the authoritative resource after a successful mutation. Do not optimistically display approval, stock availability or completed OCR before the server confirms it. On409 preserve the user input, show that data changed, and require a fresh intentional action using the new revision.
10. Attach request ID to logs and append an audit event for business changes inside the transaction. Measurements use monotonic durations and UTC event timestamps. Any reporting export is redacted and goes through analytics_outbox rather than a second uncoordinated remote write.

## REST API AND DATA FLOW
- `POST /v1/enquiries` → `f09_create_enquiry`; request `EnquiryCreate` as JSON; response `EnquiryView`, HTTP 202; access `customer`.
- `GET /v1/enquiries/{enquiry_id}` → `f09_get_enquiry`; request `None` (no body); response `EnquiryView`, HTTP 200; access `owner`.

API module calls this feature facade, which uses the foundations' domain service/repository. Customer-visible reads require ownership or active own-demo scope; staff detail reads require assignment or admin. Backend search uses the validated PostgreSQL serving version originally loaded from Snowflake. Never issue one Snowflake query per render, poll or keystroke. If the feature starts background work, commit its job and return the stored resource ID; the worker runs fixed Python steps and the client polls progress. HTTP 202 means accepted, not successful completion. For an idempotent replay, return the original status and response body. All errors follow Problem and the mapping in docs/REST_API.md.

## VALIDATION AND FAILURES
Never remove compatible-set filtering, provenance, revision checks, assigned-only real review or own-session demo isolation. Never make an LLM choose a machine, authorize a part, approve, publish, execute SQL or invoke a write tool. Do not add voice, quotation builder, order creation, inventory reservation or external-message sending. A known part number is not sufficient evidence of fitment. Free keys are not proof of available credit. No paid fallback or account upgrade is authorized. Keep live providers disabled until their dedicated allowance and expiry have been confirmed.

- Case 1: Empty and oversized input returns validation error. Arrange a fixture that reaches this boundary, call the production entry point, and assert both the response and absence of unauthorized or partial writes.
- Case 2: HTML is escaped. Arrange a fixture that reaches this boundary, call the production entry point, and assert both the response and absence of unauthorized or partial writes.
- Case 3: retry does not duplicate a message. Arrange a fixture that reaches this boundary, call the production entry point, and assert both the response and absence of unauthorized or partial writes.

Check string lengths, list bounds, UUID validity, enum values and timestamps at the boundary. Pydantic forbids unknown keys. Ownership checks precede expensive or provider operations. A syntactically valid but stale revision is409, not422. Foreign scoped records are404; unauthenticated requests401; role-only denial403. Dependency failure must preserve the previous usable state and return a recoverable code when retry is safe. Never convert missing stock to zero or a retrieval outage to no compatible parts.

## TESTS
Backend path: `tests/features/test_f09.py`. Frontend path: `apps/web/tests/features/f09.test.tsx`.

- Happy path: arrange the relevant synthetic catalogue, actor and enquiry state; execute the contract above; assert the feature-specific behavior stated in GOAL, exact status and typed response. For writes, reload PostgreSQL and inspect the audit and current revision.
- Case 1: Empty and oversized input returns validation error. Arrange a fixture that reaches this boundary, call the production entry point, and assert both the response and absence of unauthorized or partial writes.
- Case 2: HTML is escaped. Arrange a fixture that reaches this boundary, call the production entry point, and assert both the response and absence of unauthorized or partial writes.
- Case 3: retry does not duplicate a message. Arrange a fixture that reaches this boundary, call the production entry point, and assert both the response and absence of unauthorized or partial writes.
- Scope isolation: repeat with another customer/session or an unassigned reviewer; assert404 or403 according to the access table, and no leaked response fields or writes.
- Concurrency: where this feature mutates state, send two matching idempotency keys concurrently and assert one effect; send a stale expected_revision and assert409. A read-only feature instead tests stable ordering and a changed resource between polls.
- Dependency boundary: replace the relevant adapter with a timeout/failure and assert explicit degraded behavior with no publication. Unit tests must not call a real paid API.
- UI: render English and Arabic, simulate keyboard interaction, check the named error and empty states, and assert that displayed part numbers/quantities come from the response. Verify no page-wide overflow at 360px and no inaccessible primary action.

## COMMANDS AND EXPECTED RESULTS
`python tools/run_checks.py --prompt F09` must discover this feature's exact backend/UI tests and exit0 only after they pass. Run `uv run pytest tests/features/test_f09.py -q` and `corepack pnpm --dir apps/web exec vitest run tests/features/f09.test.tsx` for focused diagnosis. Run `python tools/check_contract_drift.py` after adding routes; generated OpenAPI must match the owned operations in spec/openapi.json. During incremental builds compare only completed owners; the final gate requires every operation. Expected output is real pass/fail reporting with no skipped required scenario; do not fabricate a number. Save redacted logs in `evidence/F09/`.

## MANUAL CHECK
Open the relevant page using the supplied synthetic scenario and confirm the behavior in GOAL. Switch language, resize to360px, and repeat with keyboard only. Verify current revision, source catalogue version and approved/unapproved status remain visible where meaningful. Then reproduce one listed failure and confirm that user input is preserved and no unauthorized final recommendation appears. Internal-only features are checked through their calling feature plus their CLI/test receipt rather than a fabricated screen.

## DOCUMENTATION UPDATES
Update `features/F09-bilingual-chat.md` with actual paths, commands, results, screenshots if useful, commit and remaining issues. Update docs/HANDOVER.md and append docs/SESSION_LOG.md with next step. If an API model changes, update spec/api_models.py, spec/openapi.json and generated TypeScript together; never let examples diverge. If Snowflake/SQL behavior changes, update docs/DATA_OWNERSHIP.md and migration tests. Mark the feature implemented only after its own evidence exists.

## ROLLBACK AND COMMIT
Commit as `feat(f09): implement bilingual chat`. Revert this exact commit after checking dependants; do not reset the database or revert unrelated work. Disable the panel/route before reverting a prerequisite used by other features. Any applied schema change uses a compensating migration. Retain audit, approval snapshots and immutable catalogue versions. A rollback never disables compatibility or human approval to make the demo work.

## COMPLETION EVIDENCE
Return the implemented behavior, signatures, API methods, tests with actual outcomes, and commit SHA. Explicitly separate offline tests from live Snowflake/OpenAI/hosted checks. Confirm that every failure case above was exercised and that no features were silently removed. If a provider account is unavailable, the deterministic fixture tests still run and live verification remains blocked rather than falsely passed.
