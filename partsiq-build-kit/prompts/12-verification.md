# 12 Deterministic verification and fact hashing

## GOAL
Check every requested item has exactly one current selected candidate and positive quantity.

## CONTEXT AND PREREQUISITES
The product is a bilingual spare-parts enquiry and human-review application. Snowflake stores versioned source catalogue data and redacted reporting events; Supabase supplies authentication, private files and PostgreSQL operational records. A validated PostgreSQL catalogue mirror supports compatibility checks and fast interactive reads. One FastAPI package and one background worker run the application. OpenAI extracts text/photos and writes constrained prose; ordinary Python controls all decisions. No multi-agent framework is part of this build.

Read AGENTS.md, docs/PRD.md, docs/ARCHITECTURE.md, docs/CONSTRAINTS.md, docs/TECH_SPEC.md, docs/REST_API.md and docs/WORKFLOW.md. Execute the predecessors 11 before this prompt. Read the feature matrix for downstream callers. Presence of a prior prompt file does not mean its work is implemented.

## PACKAGES AND INSTALLATION
Use the exact pins in spec/python-requirements.in and spec/web-package.json. The resolved reference locks are spec/python-requirements.lock and spec/pnpm-lock.yaml. Foundation 00 creates the development environment with `uv venv --python 3.12`; then run `uv pip sync spec/python-requirements.lock`. Foundation 18 copies the supplied web manifest and lock before `corepack pnpm --dir apps/web install --frozen-lockfile`. Do not install LangGraph, LangChain, CrewAI or an agent SDK. Snowflake uses snowflake-connector-python==4.8.0 with fixed SQL and bound parameters. OpenAI uses openai==3.19.2; FastAPI==0.135.1, Pydantic==2.12.5, asyncpg==0.31.0 and httpx==0.28.1 supply the application boundaries. Optional sentence-transformers==5.2.3 and the explicit CPU torch wheel are loaded only by the worker. Full package purpose and installation ownership are in docs/DEPENDENCIES.md.

## FILES AND OWNERSHIP
- `apps/api/partsiq/enquiries/verification.py`: implement the responsibility named by this path and the ordered instructions below.
- `apps/api/partsiq/enquiries/facts.py`: implement the responsibility named by this path and the ordered instructions below.
- `tests/foundations/test_12.py`: executable acceptance coverage for this step.

Keep this step limited to its owned files. Connect additions in the already-created application router, settings and dependency container only when they exist. Add each such modification to the completion receipt. Preserve legacy source in references/legacy-backend.zip; application paths use the single partsiq package.

## TYPED CONTRACTS
```python
async def verify_facts(facts: VerifiedFacts, evidence: VerificationEvidence) -> VerificationResult
def canonical_fact_hash(facts: VerifiedFacts) -> str
```

Contract models are defined in spec/contracts.py and spec/api_models.py. Legacy IdentifyRequest, IdentifyResponse, PartSearchRequest and PartSearchResponse remain in partsiq.search.schemas from the characterized legacy code. Path IDs are UUID except numeric catalogue IDs. Monetary usage and quantities use Decimal; timestamps are timezone-aware UTC. Settings is a pydantic-settings BaseSettings class generated from spec/environment.json. Return domain results; convert them to HTTP only in a route adapter. No domain function accepts an unverified actor supplied in a request body.

## IMPLEMENTATION STEPS
1. Check every requested item has exactly one current selected candidate and positive quantity.
2. Verify candidate membership, configuration fitment, source evidence, active catalogue version, terminal supersession validity and stock allocation bounds.
3. Aggregate allocations by warehouse and part across all items.
4. Reject unknown or duplicate hidden items and unsupported transfer estimates.
5. Serialize canonical facts with sorted keys, stable item ordering, decimal strings and UTC timestamps, then SHA256 hash.
6. Store each named rule result and its evidence identifiers.
7. Validation failure goes to staff, not a best-effort published answer.
8. No LLM is used here.
9. A known database part number alone is insufficient: it must fit the resolved configuration and requested item.
10. Reuse this exact verifier for automatic drafts, staff edits and approval.

Inject provider and database adapters so unit tests use deterministic fakes and integration tests use disposable services. Do not make network calls while holding an enquiry row lock. Separate external work from final fenced persistence. Every irreversible business mutation needs an audit record in the same transaction. Search/read operations must use the validated active catalogue version, never an arbitrary latest Snowflake row. Add explicit bounded timeouts for every dependency and map known failures to stable error codes.

## REST API AND DATA FLOW
The only public API is FastAPI under `/v1`. `apps/api/partsiq/api/router.py` includes feature routers created later. This foundation supplies domain functions; it must not invent additional competing endpoints. Read spec/endpoints.json for exact methods, resource paths, models and owners. Browser → verified route dependency → feature application function → this domain module → repository. Slow work is represented by a committed jobs row and a202 response. Worker → fixed transition table → domain function → lease-fenced PostgreSQL update. Snowflake synchronization is a separate job; no distributed transaction spans Snowflake and Supabase.

## VALIDATION AND FAILURES
Never remove compatible-set filtering, provenance, revision checks, assigned-only real review or own-session demo isolation. Never make an LLM choose a machine, authorize a part, approve, publish, execute SQL or invoke a write tool. Do not add voice, quotation builder, order creation, inventory reservation or external-message sending. A known part number is not sufficient evidence of fitment. Free keys are not proof of available credit. No paid fallback or account upgrade is authorized. Keep live providers disabled until their dedicated allowance and expiry have been confirmed.

Missing auth is401; insufficient role is403; a foreign scoped resource is404; stale revision, changed idempotency payload or stale catalogue is409; invalid typed input is422; request quota is429; a required unavailable dependency is503. Use Problem.code for machine-readable behavior and request_id for diagnosis. Do not expose database errors, secrets, private object paths or provider responses. A failed dependency must not be reported as an empty successful result.

## TESTS
Create `tests/foundations/test_12.py` with fixtures for the exact contracts above. Test the normal algorithm described in IMPLEMENTATION STEPS, each rejected boundary described there, and dependency failure without partial business writes. For data mutations use a rollback assertion and verify the audit event. For async work simulate an expired lease and a new revision before completion. For schema/infrastructure steps assert the actual SQL, configuration and installed versions rather than mocking the check itself. Keep network tests explicitly marked and never run them against production. Record separate unit, integration and hosted outcomes; no skipped required case may be called passed.

## COMMANDS AND EXPECTED RESULTS
Run `python tools/run_checks.py --prompt 12`. Expected: all named files exist, the selected tests execute, and exit status0 follows only when every required assertion passes. Run `uv run ruff check apps/api tests` and `uv run mypy apps/api/partsiq` when the package exists; fix new errors before continuing. For frontend changes run `corepack pnpm --dir apps/web test --run` and `corepack pnpm --dir apps/web typecheck`. Do not assert a fixed passing test count before executing tests. Save stdout/stderr with credentials redacted in `evidence/12/`.

## MANUAL CHECK
Exercise this module through the nearest available caller using the synthetic fixture. Inspect the input, typed output, persisted revision, source version and request ID. Repeat with one invalid input and one unavailable dependency. If this is an infrastructure prompt, verify the real account/host receipt; lack of account access is blocked, not passed. UI checks include English, Arabic, 360px width, keyboard navigation and200 percent zoom. Do not display test-only data as real client inventory.

## DOCUMENTATION UPDATES
Update docs/HANDOVER.md with step12, actual changed paths, commands, results and the next build-order ID. Append docs/SESSION_LOG.md rather than replacing previous failures. Record source/schema changes in docs/TECH_SPEC.md and the relevant ADR. Update corresponding feature traces only after their acceptance tests pass. Add runtime API changes to the canonical specification and prove contract parity. Keep all claims about accuracy, cost and latency tied to measured evidence.

## ROLLBACK AND COMMIT
Create a clean checkpoint commit before this step. Commit only this prompt as `feat(verification): implement foundation 12 deterministic verification and fact hashing`. Revert that exact commit after checking for dependent later changes. Applied database schema changes require a forward compensating migration; never reset shared Supabase or delete audit/history. Restore the previous active catalogue pointer only after validating its snapshot and stock freshness. Remote orphaned Snowflake versions stay unactivated for reconciliation. Rollback provider configuration without enabling a paid fallback.

## COMPLETION EVIDENCE
Report implemented signatures, caller/callee wiring, test commands, actual pass/fail output, manual observations, commit SHA and unresolved blockers. The coding agent must inspect its own diff and confirm no scope was silently removed. No runtime behavior is complete merely because this specification exists. Continue only when its dependencies are usable or clearly report the narrow blocker.
