# PartsIQ coding-agent operating manual

## Session start
Read AGENTS.md,docs/HANDOVER.md,docs/CONSTRAINTS.md,docs/ARCHITECTURE.md,the current prompt,and its READ FIRST files. Summarize current state and intended change in simple English. The source-of-truth order is owner decisions,approved kit contracts,legacy characterization,then implementation convenience.

## Work rules
1. Execute one implementation prompt at a time in prompts/README.md order.
2. State files,packages,tests and risks before code. The owner has approved the sequence and listed changes; continue without asking for repeated permission. Ask when a new decision exceeds that approval.
3. A source file has one creator in spec/file-ownership.json. Later prompts modify it. Keep schema,contracts,routes and environment names synchronized.
4. Preserve legacy domain code and numeric catalogue IDs. Characterize first,then make the approved corrections for successor fitment and ambiguity margins.
5. Never edit an applied migration. The candidate-key migration is explicitly approved; other destructive changes need a concrete migration and rollback proposal.
6. Secrets remain server-side. No real customer data or credentials in fixtures,logs,traces or screenshots.
7. Report actual commands and outcomes. Blocked tests are blocked,not passed. A written prompt is not an implemented feature.
8. Comments explain why,who calls the code,and assumptions that affect safety. Do not comment obvious syntax.
9. Use branch prompt/00-bootstrap for foundation00 and the corresponding ID/title for subsequent tasks. Commit each task independently.
10. Review the diff,update handover and explain the result before moving to the next task.

## Stop conditions
Stop for a new cross-service boundary,unapproved package or algorithm,reduced compatibility/verification/approval control,public demo access to real data,paid fallback,production deletion,or a contradictory requirement. Show the concrete change and smallest compliant alternative. Approved schema additions and named migrations do not require a new permission loop.

## Definition of done
Named files implemented; exact package pins retained; success/failure tests run; security and revision cases covered; documentation updated; actual implementation commit recorded; unresolved external deployment checks explicitly identified. Human approval in the product is mandatory independently of coding-agent authorization.

## Documentation habits
Apply all 15 habits mapped in docs/FIELD_GUIDE_MAP.md. Record actual coding-model identifier when available; write 'not exposed' when it is unavailable. Never invent a model version or test result.
