# Fixed Python workflow

> **SUPERSEDED (2026-10) — see `docs/adr/0001-langgraph-workflow-engine.md` (repo root).**
> The owner has adopted **LangGraph with deterministic routing** as the single authoritative
> workflow engine: fixed transitions are decided in code (`partsiq.workflow.transitions.next_step`),
> there is **no LLM supervisor**, and compatibility/verification/approval stay deterministic.
> Any statement in this document that forbids or excludes LangGraph is OBSOLETE. The
> consolidated engine lives in `apps/api/partsiq/workflow` and is proven by
> `apps/api/tests/test_workflow_langgraph.py` + `test_journey_e2e.py`.


The controller is a deterministic transition table, not an LLM router. Persist state in workflow_runs and completed outputs in workflow_step_results. The unique key is enquiry_id plus revision. A job lease and a separate input hash fence every committed result.

| Current step | Condition | Next step | Function owner |
|---|---|---|---|
| intake | Text parsed and no image pending | identify or clarify | ai.extraction.extract_message |
| intake | Validated image requires reading | await_ocr | jobs.nameplate.read_nameplate |
| await_ocr | OCR result persisted | confirm | enquiries.extraction.confirm_nameplate |
| confirm | Customer confirms identifiers | identify | workflow.resolution.resolve_items |
| identify | Missing or conflicting machine details | clarify | enquiries.questions.clarification |
| identify | One configuration resolved for each item | search | search.service.SearchService |
| clarify | New answer accepted in new revision | intake or identify | enquiries.intake.append_message |
| search | No compatible result | needs_staff | workflow.resolution.resolve_items |
| search | Close candidates | choose | enquiries.questions.clarification |
| search | Unique sufficient match | plan | enquiries.fulfilment.plan_enquiry |
| choose | Current candidate chosen | plan | enquiries.revisions.choose_candidate |
| plan | Complete or explicitly short plan | draft | ai.reply.draft_slots |
| plan | Missing/stale inventory | needs_staff | enquiries.fulfilment.plan_enquiry |
| draft | Structured slots rendered | verify | enquiries.verification.verify_facts |
| verify | All checks pass | review | workflow.repository.commit_step |
| verify | Any rule fails | needs_staff | enquiries.verification.verify_facts |
| review | Current revision approved | complete | enquiries.approval.approve |
| review | Corrected/rejected | new revision or terminal rejection | enquiries.revisions or approval |

Each transition has a typed StepOutcome with reason_code and model-validated step data. The data envelope is not permission to store arbitrary provider output. Define a concrete payload model for each step using the provided IntakeResult, MachineView, CandidateList, PlanView, ReplySlots and VerificationResult contracts. Validate the matching payload before persistence.

## Persistence algorithm

Claim a due job with FOR UPDATE SKIP LOCKED and a random lease token. Load enquiry/session and reject obsolete revision/generation. Under a short transaction, claim the matching workflow run. Release locks before calling OpenAI, Storage or Snowflake. Hash the exact step inputs and reuse only an identical completed result. Perform one bounded step. Reacquire row lock, recheck lease/revision/generation, write output and next state, append audit, then commit. Schedule the next step or park at a waiting state. Renew leases while healthy; never let an expired process finalize a result. Stop after20automatic transitions in one job.

No transaction remains open across a provider call. There is no promise of exactly-once external API execution; uncertain provider completions remain conservatively charged/reserved. Business publication is effectively once through idempotency and a unique recommendation-per-revision index.

## User changes

New facts or item choice invalidate derived data by creating a new revision. Preserve old outputs for audit but do not reuse them without matching input hash and source version. Assignment and notes need not change the extraction revision unless they alter facts. An assignment has its own audit event and immediate access effect. Reset increments demo generation and makes old jobs obsolete. User questions are code-owned bilingual templates and do not require staff approval because they make no final part recommendation.

## Cross-feature dependencies

Search and verification share one source of fitment truth. Draft rendering consumes VerifiedFacts only. Approval rechecks freshness and fact hash. PDF uses ApprovedSnapshot only. Analytics observes committed business events and cannot block approval. AI allowance remains local and authoritative even when traces or Snowflake reporting are unavailable.

## Missing quantity before item materialization

IntakeResult permits a null quantity because absence is not permission to assume one. Keep provisional item identifiers and their extracted fields in the typed workflow state until quantity is confirmed. Do not insert a null or invented quantity into enquiry_items, whose quantity constraint is intentionally positive and non-null. Clarification tracks the provisional item identifier in state; once confirmed, materialize that item with the same UUID and current revision. Persist the original extraction separately for audit. Tests must cover multiple items where only one quantity is missing.
