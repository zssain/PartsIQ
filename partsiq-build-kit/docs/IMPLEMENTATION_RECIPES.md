# Implementation recipes

## Fixed transition dispatch

Define STEP_HANDLERS as a static mapping from WorkflowStep to an injected async function. A handler receives typed current state and returns StepOutcome. next_step uses explicit conditions from WORKFLOW.md and rejects a transition not in the allowed table. There is no prompt that asks a model which function to call. During early foundation work, inject deterministic test handlers; wire production handlers when their owning foundations exist. Avoid importing future modules merely to satisfy a type annotation.

The runner calculates the input hash before work, checks workflow_step_results for a matching completed value, and performs external calls outside a row lock. On completion, it uses a transaction with SELECT FOR UPDATE on the enquiry and verifies job lease token, current revision and demo generation. Only then can it insert step results and advance state. A failed check returns obsolete and discards output. Tests pause a fake provider call, change the revision, and then release the call to prove stale results cannot commit.

## Idempotency transaction

Hash canonical request JSON together with authenticated actor, HTTP method and normalized route path. Insert an idempotency record under its unique scope/key. If the existing hash differs, return409. If the operation is completed, replay its stored status/body. If it is still in progress, return a stable conflict/retry response rather than running it again. The business write, job creation, audit and saved response occur in one transaction. A process crash before commit leaves no partial accepted request. External provider calls occur later in jobs, not inside this transaction.

## Catalogue hash and identity

Sort records by(entity_type, entity_key). Serialize each payload as UTF-8 JSON with sorted keys, no insignificant whitespace, decimal strings and normalized timestamp format. Exclude generated search_document and volatile import timestamps. Hash the complete canonical record stream with SHA256. Validate unique keys before constructing a lookup dictionary. Reusing VERSION_ID with different content is an integrity error. Preserve leading zeros in serial text while separately validating numeric ranges. Numeric IDs for new entities are allocated before sealing the source version and retained on every retry.

## Compatibility and ranking

Resolve exactly one model configuration. Load only the active version's explicit part_compatibility rows for that configuration. Reject missing source references. Pass that allowed ID set into lexical and semantic candidate retrieval so an incompatible perfect textual match never reaches scoring. Combine scores using the characterized legacy formula and deterministic tie order. Calculate the best-versus-runner-up margin before truncating results. A request for limit1 does not remove evidence of ambiguity. Use code-owned thresholds and labelled evaluation cases; do not call a score a calibrated probability.

## Quantity allocation

Build total demand per part across all enquiry items. For each part, read the same stock snapshot, calculate available=max(0, on_hand-reserved) only after validating the source values, and allocate local stock first. Sort reachable warehouses deterministically by approved transfer duration and stable warehouse ID. Never invent a missing route. Subtract each allocation from one shared in-memory availability ledger before allocating another item. Report shortage explicitly. A planner does not mutate stock or create a reservation. Approval reruns the checks against the current snapshot and freshness policy.

## Fact-bound reply

The LLM returns only ReplySlots. Code renders part numbers, quantities, warehouses, estimates and references from VerifiedFacts. Reject or replace model slots containing unsupported identifiers or quantitative claims. Serialize and hash the verified facts independently of prose. Store the draft with revision, catalogue version and fact hash. An edit cannot directly set approval. Approval locks and revalidates the current state before inserting decision, recommendation and audit together. A known database number that is incompatible still fails verification.

## Redacted reporting outbox

Write a small analytical event in the same business transaction. Export only EVENT_ID, EVENT_TYPE, OCCURRED_AT, IS_DEMO, STATUS, STAGE, DURATION_MS, INPUT_TOKENS, OUTPUT_TOKENS and ESTIMATED_COST_USD. Reject any extra field before building SQL. MERGE by EVENT_ID under a single exporter lease using bound parameters. Compare identical existing data on replay; conflicting data is an integrity error. Save Snowflake query ID and acknowledge locally only after success. Never export raw customer text, serials, notes, photos, keys or signed URLs.

## REST adapter example

A feature router declares response_model and explicit success status. Its verified actor dependency executes before the facade. The facade receives path IDs, typed command and idempotency key; it rejects mismatching enquiry IDs in the body. It invokes one domain function and maps named domain failures through the shared Problem handler. A browser sends only candidate ID or corrected fields, never an authoritative fitment fact. UI state is refreshed after writes. On409, it preserves unsent input and requires a fresh action against the new revision.

## Test fixtures and replay

Use a fake clock, isolated database transaction, test actor factory and deterministic provider adapter. Keep at least two customers, two demo sessions, assigned/unassigned reviewers and an admin in permission fixtures. The four demonstration fixtures are not the entire evaluation dataset. Add independent Arabic variants, serial endpoints, wrong part numbers and duplicate-part allocation cases. Store expected compatible IDs and clarification outcomes from reviewed catalogue facts. Never change expected outputs simply because the implementation produced a different answer.
