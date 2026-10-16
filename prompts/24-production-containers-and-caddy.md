# 24 - Production containers and Caddy
PHASE: Infrastructure   DEPENDS ON: 22   RISK: high

## GOAL
Build immutable service images; pin base image digests from verified registry manifest. Preserve gateway/search Dockerfile lineage and modify them explicitly. One search process avoids duplicate model memory. Separate worker,sweeper and orchestrator event-consumer commands; private Docker network for internal ports; publish only Caddy80/443. Add read-only rootfs where possible,tmpfs for PDF,bounded logs and resource limits measured during smoke. Use no Kubernetes or public Redis.

## READ FIRST
- AGENTS.md
- docs/HANDOVER.md
- docs/CONSTRAINTS.md
- docs/ARCHITECTURE.md sections 2 and 4
- docs/TECH_SPEC.md
- docs/CONTRACTS.md
- docs/FLOW.md
- spec/file-ownership.json


## PLAN CHECK
State the exact files to create/modify, packages, validation commands and risk before implementation. The approved build sequence authorizes these listed changes. Ask only if a new decision changes locked scope, introduces a destructive action or crosses a boundary. Do not repeatedly ask for approval already granted. Verify prerequisite prompts are complete, not merely present as documents.

## PACKAGES
No new package. Use the existing exact pins and committed locks; do not install a second library for this feature.

## FILES TO CREATE
- `docker-compose.prod.yml`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `Caddyfile`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/orchestrator/Dockerfile`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/worker/Dockerfile`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `infra/verify_images.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `infra/images.lock.json`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `tests/foundations/test_24.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.

Typed entry contracts:

def verify_images(compose_file: Path) -> list[str]: reject mutable application tags,missing healthchecks,public internal ports and embedded credentials.

Implementation sequence:
1. Build immutable service images; pin base image digests from verified registry manifest.
2. Preserve gateway/search Dockerfile lineage and modify them explicitly.
3. One search process avoids duplicate model memory.
4. Separate worker,sweeper and orchestrator event-consumer commands; private Docker network for internal ports; publish only Caddy80/443.
5. Add read-only rootfs where possible,tmpfs for PDF,bounded logs and resource limits measured during smoke.
6. Use no Kubernetes or public Redis.

## FILES TO MODIFY
- `services/gateway/Dockerfile`: connect the new implementation through the existing owner; preserve callers and add regression coverage.
- `services/search/Dockerfile`: connect the new implementation through the existing owner; preserve callers and add regression coverage.

## HOW IT CONNECTS
Owner: Infrastructure; ARCHITECTURE.md section2. FLOW.md row `24` identifies the entry contract and preceding owners. Required predecessors: 22. HTTP routes call application functions,which invoke domain rules and infrastructure adapters. Specialist tools are read-only. Gateway passes verified identity and request ID; worker events carry revision and lease generation. Register new routes in the named existing entry point; never create a parallel public backend.

## CONSTRAINTS FOR THIS STEP
Preserve legacy domain names and compatible-set filtering. OpenAI only through common client. BGE-M3 only in search. Assigned-only real review; own-session demo review. No final recommendation without current-revision approval. No paid fallback,external message,quotation,voice,reservation or order creation. Document assumptions as measured facts or explicit configuration,never as guarantees.

## ACCEPTANCE TESTS
- `tests/foundations/test_24.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.

`python tools/run_checks.py --prompt 24` must exit0 and report all named tests passed, with no required test skipped. It dispatches each service test in its own process and runs UI tests through pnpm. Before that runner exists, prompt00 creates and tests it using the standard library. Do not fabricate a passing count. Record actual output in the feature trace. Test databases must be disposable local Supabase; no production reset.

## MANUAL VERIFICATION
Run the relevant demo path for production containers and caddy using synthetic fixtures. Inspect customer view and assigned-reviewer view where applicable. Confirm the success outcome,then exercise at least one listed failure. Inspect persisted revision,audit event and request ID without exposing secrets. For UI,check Arabic,keyboard operation and 360px width. For infrastructure,save the real provider/preflight receipt; missing account access is blocked,not passed.

## DOC UPDATES
Update docs/HANDOVER.md with completed step `24`, actual commands, blockers and next ID from prompts/README.md. Append docs/SESSION_LOG.md with actual model identifier if exposed,otherwise 'not exposed'. Record decision changes in docs/DECISIONS.md; update matching FLOW row and file-ownership manifest for approved additions. Update docs/TECH_SPEC.md schema/package receipts only after comparing reality. Set each affected feature trace to done only when its tests pass; retain original failures and corrective evidence.

## ROLLBACK
Before edits create `git tag pre-24` if absent. Commit this task independently. To undo,run `git log -1 --format=%H`,verify the displayed commit is this task,then `git revert --no-edit HEAD`. Do not revert unrelated later work. Applied SQL requires a new compensating migration and backup review; never reset production. Publication history and audit are retained. Deployment rollback selects previous immutable images and a schema-compatible release as described in docs/ROLLBACK.md.

## COMMIT
`feat(infrastructure): 24 production containers and caddy`

## DONE WHEN
- [ ] Exact paths and contracts implemented.
- [ ] Listed tests executed with actual evidence.
- [ ] Failure and permission cases pass.
- [ ] No forward runtime dependency introduced.
- [ ] Documentation and feature traces updated.
- [ ] Diff reviewed; no unrelated change.
- [ ] Commit recorded; unexecuted deployment checks remain explicitly blocked.
