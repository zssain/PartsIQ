# Nonnegotiable constraints

> **SUPERSEDED (2026-10) — see `docs/adr/0001-langgraph-workflow-engine.md` (repo root).**
> The owner has adopted **LangGraph with deterministic routing** as the single authoritative
> workflow engine: fixed transitions are decided in code (`partsiq.workflow.transitions.next_step`),
> there is **no LLM supervisor**, and compatibility/verification/approval stay deterministic.
> Any statement in this document that forbids or excludes LangGraph is OBSOLETE. The
> consolidated engine lives in `apps/api/partsiq/workflow` and is proven by
> `apps/api/tests/test_workflow_langgraph.py` + `test_journey_e2e.py`.


- All 69 feature groups remain; voice and quotation builder stay excluded.
- One application package and fixed Python workflow. No LangGraph, supervisor, specialist-agent team or LLM-selected next steps.
- LLMs extract and draft only. Compatibility, stock allocation, verification and approval are code-controlled.
- Snowflake source versions are immutable and explicitly validated. PostgreSQL owns the active serving pointer and transactional application integrity.
- No incompatible candidate can enter the ranked set. Supersession does not imply fitment inheritance.
- Missing serials, unconfirmed OCR and close scores trigger clarification/review.
- Every final recommendation requires current human approval and audit; clarifying questions do not require approval.
- Real review is assignment scoped; demo review is own-session scoped. Demo generation/expiry are checked at final job commit.
- Private files stay private; customers receive compatibility references, staff receive authorized evidence viewer access.
- BGE-M3 runs only in the worker search module; lexical mode remains usable when semantic capability is disabled.
- No paid fallback. Live OpenAI, Snowflake and hosting require confirmed account-specific allowance. Zero budget is not a promise of free services forever.
- No order/reservation/payment/external message is created. Warehouse planning is an estimate from a timestamped snapshot.
- No production reset or automatic dependency upgrade. Migration-owner credentials never run the application.
- Audit is append-only for runtime roles, not mathematically tamper-proof against database owners.
- No raw prompts, photos, keys, JWTs or signed URLs in telemetry. Analytics exports only allowlisted fields.
- Claims about performance, accuracy, availability, client adoption and hosted status require actual receipts.
