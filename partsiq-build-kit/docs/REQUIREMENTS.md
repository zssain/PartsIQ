# Product requirements document

## Purpose and success criteria

PartsIQ helps customers describe equipment spare-part needs and helps staff prepare a defensible response. The system reduces manual interpretation and catalogue searching while keeping compatibility, quantity allocation and final approval under deterministic control. A successful recruiter demonstration shows the full enquiry journey, one ambiguity case, one incompatible request and one warehouse split, including visible provenance and human review.

Acceptance is behavioral rather than a claimed accuracy number: an incompatible exact-number match must never be recommended; unconfirmed photo identifiers must not drive matching; ambiguous candidates must not be silently selected; an unassigned reviewer must not see real enquiries; and a recommendation must not publish without a matching approved revision. Performance and extraction accuracy are measured later using the supplied evaluation plan.

## Actors and permissions

Public visitor reads the landing page and architecture. Anonymous demo customer owns an expiring demo session and can switch to reviewer presentation only for that session. Invited customer owns real enquiries when real onboarding is enabled. Reviewer sees assigned real enquiries and can correct, draft, approve or reject. Catalogue administrator stages, validates and publishes source versions. Administrator manages assignments, allowances, evaluation curation and aggregate reporting. Runtime worker identities are technical roles, not human roles.

## Main user journey

Customer creates an enquiry with destination warehouse and up to20 requested items. Optional images are privately uploaded, validated and read in the background. Structured extraction preserves the original message and source spans. The customer confirms photo identifiers and answers missing-information questions. Machine identification resolves one configuration. Search retrieves only explicitly compatible parts and supplies evidence. Close scores trigger a choice or review. Fulfilment combines repeated-part demand across items and reports availability, shortage and transfer estimates without reserving stock. A constrained draft is verified and presented to staff. Approval rechecks revision, catalogue and stock before atomically recording the decision and publishing the customer reply. Approved information can be exported as a bilingual enquiry PDF.

## Complete feature scope

Every feature below remains mandatory unless its behavior explicitly describes a capability flag, such as optional semantic ranking. Optional capability means implemented and testable with a transparent disabled mode, not silently omitted.

### F01 Branded landing

Explain the enquiry-to-approval journey; show synthetic-demo notice; expose Start demo and architecture links; display the supplied bilingual logo without stretching.

Acceptance and failure boundaries: Missing repository link hides that action; logo has meaningful alternative text; no affiliation claim.

### F02 Demo scenarios and assets

Seed four deterministic scenarios: mixed-language photo, missing serial, incompatible part, local shortage; derive identifiers from seed 42; validate expected outcomes against generated records.

Acceptance and failure boundaries: Reject a scenario whose expected part lacks compatibility; reject stock claims not supported by fixture quantities.

### F03 Demo role switching

Switch the presentation between customer and reviewer using the same anonymous identity and session; authorize review only for enquiries belonging to that active session.

Acceptance and failure boundaries: Forged reviewer role never grants staff membership; another visitor's enquiry returns 404.

### F04 Demo isolation

Bind each session to verified anonymous Supabase identity; check generation and expiry on every read, write and worker completion; exclude demos from operational metrics by default.

Acceptance and failure boundaries: Expired, reset and foreign sessions fail; missing identity context returns no rows.

### F05 Demo reset

Lock session; increment generation; cancel unfinished jobs from prior generation; enqueue Storage cleanup; keep minimal audit; create fresh scenario enquiries on explicit selection.

Acceptance and failure boundaries: Late OCR from old generation cannot update current data; repeated reset idempotency key returns the same generation.

### F06 Responsive layouts

Support 360, 768, 1280 CSS-pixel widths; stack review panels; horizontally scroll comparison tables within their region; preserve sticky primary review actions without covering content.

Acceptance and failure boundaries: No page-wide horizontal overflow; zoom 200 percent remains usable; mobile dialogs retain visible close action.

### F07 Arabic and English interface

Use a locale cookie and complete en/ar message catalogs; persist preference; set document lang and dir; isolate serials, numbers and part identifiers with bdi.

Acceptance and failure boundaries: Missing translation fails tests; language switch preserves enquiry ID and unsent draft; mixed Arabic identifiers remain readable.

### F08 Light and dark themes

Use CSS semantic tokens; initialize from saved preference then system setting; expose accessible toggle; honor reduced motion and browser color-scheme.

Acceptance and failure boundaries: No hydration mismatch; chart colors and focus rings meet contrast checks; storage-disabled browsers still work.

### F09 Bilingual chat

Accept Arabic, English and mixed text; preserve original message; detect preferred reply locale; render customer messages immediately after successful persistence.

Acceptance and failure boundaries: Empty and oversized input returns validation error; HTML is escaped; retry does not duplicate a message.

### F10 Structured extraction

Extract item descriptions, quantities, urgency and machine hints with strict structured outputs; preserve source spans; missing quantity becomes a clarification rather than assumed order quantity.

Acceptance and failure boundaries: Unknown keys and invalid quantities reject the response; unsupported model output cannot progress to search.

### F11 Clarifying questions

Use workflow reason codes to choose code-owned bilingual questions; persist pending question; associate answer with item; rerun affected resolution only.

Acceptance and failure boundaries: No final recommendation before approval; contradictory answer requires confirmation; repeat event creates one question.

### F12 Conversation memory

Persist all messages and typed current state; compact context using retained structured facts; resume by enquiry/revision; never mix customer sessions.

Acceptance and failure boundaries: Restart retains unresolved questions; old revision events are ignored and audited; foreign thread ID denied.

### F13 Private uploads

Create pending attachment and unique object path; use signed upload; validate actual bytes and magic type after confirmation; strip EXIF and cap decoded pixels before OCR.

Acceptance and failure boundaries: Wrong MIME, oversized content, image decompression bomb, duplicate confirmation and nonexistent object handled explicitly.

### F14 Nameplate OCR

Read validated nameplate via OpenAI vision; return model_text, serial_text, issues and source attachment; persist result only with current lease and revision.

Acceptance and failure boundaries: Unreadable fields remain null; vision instructions in photo are untrusted; timeout is bounded and creates recoverable status.

### F15 OCR confirmation

Show cropped or original nameplate beside extracted identifiers; require user confirm or correction; record actor and time; preserve leading zeros in serial text.

Acceptance and failure boundaries: Unconfirmed OCR never authorizes matching; blank corrected serial triggers missing-serial flow; stale confirmation returns 409.

### F16 Photo quality feedback

Check decodability, dimensions and blur heuristic before paid call; return actionable retake instructions; mark heuristic as advisory; allow a readable image despite noncritical blur warning.

Acceptance and failure boundaries: Unsupported format rejected; dark or low-resolution sample gets guidance; no fabricated OCR confidence percentage.

### F17 Multi-part enquiries

Track up to 20 items with independent quantity, machine, candidate selection and status; clarify individual items; verify aggregate allocation for repeated part requests.

Acceptance and failure boundaries: One unresolved item blocks final all-items approval; allocations across duplicate parts cannot double count available stock; zero quantity rejected.

### F18 Progress timeline

Show persisted stages, wait reason and last update; poll with bounded backoff; reconnect using server state; separate waiting for customer from waiting for staff.

Acceptance and failure boundaries: No fake completed progress; failed poll retains last state and offers retry; hidden tabs reduce polling.

### F19 Enquiry history

Return cursor-paginated owned history with status and created time; filter active demo generation; link to full conversation; use stable created_at/id ordering.

Acceptance and failure boundaries: Foreign owner ID ignored; invalid cursor returns 422; equal timestamps do not duplicate or skip records.

### F20 Machine identification

Preserve identify_machine logic for model, serial and rating; return resolved configuration or explicit missing/ambiguous status; normalize numeric serial only after preserving input.

Acceptance and failure boundaries: Boundary serials match exactly one configuration; overlapping ranges fail Snowflake publication validation and PostgreSQL serving-cache insertion; conflicting hints never silently override.

### F21 Machine mismatch detection

Compare model and serial together; return mismatch reason with safe next question; prevent retrieval while identity unresolved.

Acceptance and failure boundaries: Valid serial of a different model does not match requested model; nonnumeric serial handled without crashing.

### F22 Compatibility gate

Fetch authoritative fitment set first; rank only members; carry source_reference and catalogue version through every candidate.

Acceptance and failure boundaries: A perfect lexical match outside fitment is absent; empty fitment returns unavailable; blank provenance cannot be published.

### F23 Aliases and typo matching

Preserve Arabic normalization, part-number keys, phrase scoring and fuzzy token matching; remove machine terms using resolved model context.

Acceptance and failure boundaries: Arabic part words are not removed as machine words; exact part number outranks unrelated fuzzy alias; normalization parity test matches SQL.

### F24 Semantic retrieval

Load one BGE-M3 encoder in the worker search module; use normalized 1024-d vectors; retain legacy weighted fusion; fall back to lexical on unavailable embedding path.

Acceptance and failure boundaries: Wrong dimension rejected; no model loaded in API process; no semantic candidate outside compatible IDs.

### F25 Ranked candidates

Return top candidates with lexical/semantic evidence and deterministic tie order; compute runner-up margin before applying response limit.

Acceptance and failure boundaries: Limit one still reports ambiguity; empty set returns no candidate; NaN scores rejected.

### F26 Ambiguity handling

Use tested score and margin thresholds in code; ask customer to distinguish fuel filter versus separator; allow staff to select only verified candidates.

Acceptance and failure boundaries: LLM cannot override low confidence; unavailable candidate choice returns 409; thresholds evaluated on labelled cases.

### F27 Match explanations

Show actual alias, machine configuration, supersession chain and fitment reference; derive explanations from search evidence rather than invented model prose.

Acceptance and failure boundaries: Absent evidence shown as unavailable; user HTML is escaped; scores never labelled calibrated probability.

### F28 Compatibility references

Resolve source_reference to version-specific document and page; retain citation with every candidate and approval snapshot.

Acceptance and failure boundaries: Missing source file blocks evidence viewer and flags review; mismatched version fails verification.

### F29 Evidence page viewer

Authorize assigned reviewer or own demo reviewer; request short-lived backend-signed PDF URL; open exact cited page; label synthetic document.

Acceptance and failure boundaries: Customer receives reference only; arbitrary Storage key rejected; expired link can be renewed after authorization.

### F30 Old part numbers

Follow supersession chain with cycle protection; display old and current numbers; verify current successor has explicit fitment for resolved configuration.

Acceptance and failure boundaries: Cycles rejected; inactive terminal part returns unavailable; inherited compatibility without source is rejected.

### F31 Candidate comparison

Compare two or three candidates from the same item/revision; show number, names, evidence and warehouse availability; selecting a candidate sends its ID, not browser-authored facts.

Acceptance and failure boundaries: Foreign candidate or stale revision rejected; missing attribute shown as unavailable; keyboard navigation works.

### F32 Warehouse stock

Show available quantity as on_hand minus reserved; include timestamp and warehouse name; keep display and planner using same snapshot.

Acceptance and failure boundaries: Negative stock blocked; stock unavailable never displayed as zero without explanation; unknown warehouse rejected.

### F33 Fulfilment planning

Allocate local stock first then reachable warehouses deterministically; compute shortage; use quantity units; do not reserve stock or create orders.

Acceptance and failure boundaries: Total allocations never exceed request or stock; fractional quantities respect unit policy; unavailable transfer route cannot be invented.

### F34 Transfer estimates

Carry integer transfer_days from approved route; show estimate and source warehouse; local availability means zero transfer days.

Acceptance and failure boundaries: No route gives unknown/unavailable plan rather than invented one-day promise; estimate labelled non-guaranteed.

### F35 Stock freshness

Compare stock timestamp with configurable freshness limit; mark stale data in review; re-read current stock during approval; invalidate plan when allocation no longer possible.

Acceptance and failure boundaries: Future timestamp flagged; changed stock returns 409 and reruns planning; stale stock never becomes a delivery guarantee.

### F36 Staff inbox

List assigned operational enquiries and own active demo enquiries; filter status, priority, overdue and text; paginate stably; show counts in same access scope.

Acceptance and failure boundaries: Unassigned real enquiries hidden from reviewer; admin can see all; filters do not leak global counts.

### F37 Review workspace

Assemble current extraction, items, candidates, evidence, stock, draft and timeline; show verification failures; separate staff-only notes from customer messages.

Acceptance and failure boundaries: Missing panels show explicit empty states; stale revision disables approval; unassigned reviewer receives 404.

### F38 Correct extracted details

Lock enquiry; compare expected revision; apply typed allowed corrections; increment revision; invalidate derived selections/draft/approval; enqueue recomputation; record before and after.

Acceptance and failure boundaries: Unknown field rejected; old revision returns 409; correction cannot directly set approved status or invent candidate facts.

### F39 Review actions

Approve only verified current draft; edit prose through controlled schema then reverify; reject with reason; record actor and idempotency key.

Acceptance and failure boundaries: Double-click publishes once; concurrent edit defeats stale approval; failed verification blocks publication.

### F40 Approval invalidation

Bind approval to revision and verified fact hash; any identity, quantity, selection or catalogue-sensitive change requires new draft and approval.

Acceptance and failure boundaries: Old approval cannot authorize new revision; late workflow update cannot overwrite approved current state.

### F41 Internal notes

Append reviewer notes with author and timestamp; show only in staff workspace; prohibit customer/PDF exposure; escape rendered content.

Acceptance and failure boundaries: Empty or over-4000-character note rejected; customer route never includes note text; unassigned staff denied.

### F42 Assignments

Admin assigns active reviewer or unassigns; persist assignment history atomically; access changes immediately; demo reviewer access remains session-scoped.

Acceptance and failure boundaries: Non-admin assignment denied; disabled/nonreviewer assignee rejected; previous reviewer loses access on next request.

### F43 Overdue indicators

Set due_at using configurable urgent/normal thresholds; display overdue only for unresolved states; sort overdue first when requested; store all times UTC.

Acceptance and failure boundaries: Approved/rejected items never overdue; daylight-saving display does not change deadline; thresholds not described as contractual SLA.

### F44 Conversation summary

Produce staff-only concise summary from authorized messages and confirmed fields; store message IDs and revision; use shared budget wrapper; regenerate on relevant change.

Acceptance and failure boundaries: Outdated summary labelled stale; instructions inside messages ignored; exhausted budget leaves full conversation available.

### F45 Reply drafting

Generate greeting, explanation and closing as structured slots; code inserts all numbers and allocations; choose Arabic or English from confirmed preference.

Acceptance and failure boundaries: Unapproved critical facts never rendered; unsupported slots rejected; provider failure permits staff-authored controlled draft.

### F46 Verification gate

Check item/configuration/candidate membership, provenance, catalogue version, selected quantities and allocation bounds; compute canonical fact hash; store named rule results.

Acceptance and failure boundaries: Unknown part, incompatible part, stale catalogue, oversold plan and hidden extra item each fail a specific rule.

### F47 Human publication gate

Only approval service inserts recommendation messages; lock enquiry and recheck role, revision and verification; unique publication index prevents duplicates.

Acceptance and failure boundaries: No background job write tool can publish; database rejects recommendation lacking matching approved decision.

### F48 Input isolation

Treat customer text, OCR and imported evidence as data; separate trusted instructions; bound inputs, transitions, steps and output size; never execute model-produced templates.

Acceptance and failure boundaries: Prompt injection cannot call privileged functions, change roles or reveal secrets; model result with rogue instructions remains inert.

### F49 Audit trail

Append actor, request, entity, revision and minimal before/after metadata for AI suggestions and human changes; redact secrets and full sensitive payloads.

Acceptance and failure boundaries: Application UPDATE, DELETE, TRUNCATE fail; audit write failure rolls back approval; database-owner powers documented honestly.

### F50 Durable workflows

Persist workflow_runs and workflow_step_results in PostgreSQL; run a fixed Python transition table with durable jobs; serialize each enquiry and fence completion by revision and lease token; recover after restart without LangGraph.

Acceptance and failure boundaries: Duplicate jobs cannot repeat publication; stale revisions are discarded; interrupted steps resume from committed results; no LLM chooses the next step.

### F51 Background jobs

Persist job before Redis dispatch; dispatcher claims by ID; sweeper redispatches pending/expired jobs; worker handles OCR, PDF, imports and cleanup.

Acceptance and failure boundaries: Redis loss does not lose DB job; unavailable Redis rate limiter fails closed; heavy work never blocks HTTP intake.

### F52 Retry and deduplication

Claim with FOR UPDATE SKIP LOCKED; assign lease token; heartbeat; retry transient errors with backoff up to max attempts; fence final writes by lease token.

Acceptance and failure boundaries: Expired worker cannot commit; permanent validation failure not retried; provider timeout marked uncertain and budget held conservatively.

### F53 Graceful failures

Map stable error codes to bilingual recovery guidance; distinguish validation, quota, service outage and staff-required states; preserve user input.

Acceptance and failure boundaries: No raw stack traces or keys; retry only safe idempotent action; search lexical fallback clearly reported.

### F54 Access and permissions

Verify Supabase issuer, audience, signature, expiry; derive identity server-side; enforce assigned-only review; keep credentials server-side; disable public real-client signup.

Acceptance and failure boundaries: Forged role claim ignored; missing context denies rows; preview cannot reach prod database; demo cannot publish shared catalogue.

### F55 Saved machines

Save confirmed model and serial with user label; list own active entries; archive entry; prefill a new enquiry but re-identify against current catalogue.

Acceptance and failure boundaries: Duplicate label permitted with distinct ID; foreign ID denied; stale configuration never reused as authoritative.

### F56 Repeat enquiry

Copy customer request and confirmed hints into a new enquiry; issue new ID/revision; link origin in audit; run matching, stock and review again.

Acceptance and failure boundaries: Never copy approval, allocation, draft or signed file URL; source ownership required; repeated submission deduplicated.

### F57 Catalogue browser

Read published catalogue with model/category/text filters; page results; show part detail and supersession; staff can inspect fitment and sources.

Acceptance and failure boundaries: No unpublished import rows exposed; missing number returns 404; literal query cannot become SQL.

### F58 Catalogue imports

Read CSV UTF-8 or XLSX without evaluating formulas; validate row schema, references, serial overlap, supersession cycles and source evidence; show dry-run report; explicit admin publish. Stage a version in Snowflake, validate all relationships explicitly and only then activate a validated PostgreSQL serving snapshot.

Acceptance and failure boundaries: Invalid batch changes no published data; file with macros/formulas rejected; 50000-row and 10MiB limits enforced; public demo cannot publish.

### F59 Catalogue versioning

Store immutable versioned catalogue records in Snowflake; verify record counts and canonical SHA256; stage the PostgreSQL serving snapshot; atomically switch the active version in a PostgreSQL transaction; retain published historical records; reconcile partial remote writes.

Acceptance and failure boundaries: Two publishers cannot leave two active versions; failed publish rolls back; old approval retains immutable evidence snapshot.

### F60 Missing-parts queue

Record unresolved item once; allow assigned staff to mark investigating, resolved or unavailable with note; link back to enquiry; no automatic catalogue creation.

Acceptance and failure boundaries: Resolved status requires staff explanation; foreign item denied; empty search result is not fabricated stock.

### F61 Enquiry PDF

Export approved revision only; render logo, bilingual customer text, verified selections, estimates and references; embed Arabic fonts; store private object and signed download.

Acceptance and failure boundaries: Exclude notes and secrets; stale or unapproved revision rejected; long Arabic names wrap without clipping; no prices or quotation title.

### F62 Labelled evaluations

Include four demos plus Arabic, typo, serial-boundary, ambiguity, stock and injection cases; record expected compatible set and clarification outcome; run deterministic suite without API calls.

Acceptance and failure boundaries: No self-reported model confidence as accuracy; evaluation fixture disjoint from examples used in prompts; failures keep actual output.

### F63 Metrics dashboard

Show volume, status, review time, clarification and labelled accuracy with denominators; separate demo traffic; filter time window; scope reviewer data to assignments. Export redacted aggregate events to Snowflake through an outbox and show reporting freshness separately from live operational counts.

Acceptance and failure boundaries: Zero denominator displays unavailable; no fabricated percentage; demo traffic never silently improves operational metrics.

### F64 Latency and AI cost

Measure stages with monotonic clock; log model/token usage and estimated cost; reserve confirmed free credit before each attempt; expose consumed/reserved allowance.

Acceptance and failure boundaries: Unknown price or expired credit blocks calls; concurrent reservations cannot exceed cap; API key validity never implies free credit.

### F65 Correction feedback

List authorized before/after corrections; let admin curate anonymized labelled eval cases; record reviewer and source revision; never auto-train on unreviewed edits.

Acceptance and failure boundaries: Private text excluded from exported fixtures; duplicate case source detected; unreviewed correction cannot become ground truth.

### F66 Tests and CI

Run service-isolated Python tests, frontend checks, RLS integration and deterministic evals; build images; require explicit environment approval for deployment; pin action SHAs.

Acceptance and failure boundaries: No prod DB in tests; no secret available to untrusted fork jobs; failed gate blocks deployment.

### F67 Traces

Propagate request/enquiry/job IDs; capture stage timing and safe status; export optional Langfuse traces with payload redaction; operate normally when tracing unavailable.

Acceptance and failure boundaries: No raw key or full photo logged; exporter outage never breaks approval; budget accounting remains local and authoritative.

### F68 Recruiter documentation

Write concise overview, real architecture, quick start, demo paths, tests, trade-offs and limitations; link measured evidence; explain deterministic decisions and ordinary Python functions.

Acceptance and failure boundaries: No invented accuracy, uptime, client relationship or production adoption; distinguish implementation status from specification.

### F69 Demo walkthrough

Create 3-minute and 8-minute scripts covering happy path, missing serial, incompatibility, stock split and human review; include recording checklist and captions.

Acceptance and failure boundaries: Do not claim video exists until recorded; use synthetic data; show failure handling and reset; verify links before sending recruiters.

## Nonfunctional requirements

Security: server-verified identity, scope checks, RLS, private files, least-privilege data roles, redacted logging and no model-authorized writes. Durability: database-backed jobs, leases, fencing, idempotent API writes and recoverable partial Snowflake synchronization. Language: Arabic/English UI and replies, mixed-script identifiers, bidi isolation and bundled Arabic PDF fonts. Accessibility: keyboard operation, visible focus, reduced motion, 200 percent zoom and360px minimum layout. Maintainability: typed models, one domain implementation per rule, versioned migrations and explicit test evidence.

Provisional performance goals are local acceptance budgets, not measured claims: API writes should acknowledge without waiting for AI or warehouse work; provider operations have bounded timeouts; polling uses backoff; optional embeddings cannot prevent lexical readiness. Benchmark the actual host before setting public latency claims. The paid budget is zero; the system requires confirmed free allowance before live provider calls. Real-client retention is an onboarding decision; until it is recorded, real onboarding stays disabled. Demo access expires after24hours and background cleanup follows the documented policy.

## Exclusions

No voice input, quotation builder, prices, payments, orders, stock reservations, automatic WhatsApp/email sending, multi-agent routing, autonomous SQL generation or automatic training on staff corrections. No claim of perpetual free cloud hosting. No invented partnership with equipment distributors.
