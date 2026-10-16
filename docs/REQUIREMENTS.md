# Approved requirements

Recruiter-facing bilingual spare-parts enquiry system with deterministic compatibility and human approval. All original selected behaviours retained by grouping scenario/photos asF02 and access/roles asF54. No voice or quotation builder.

| ID | Feature | Behaviour |
|---|---|---|
| F01 | Branded landing | Explain the enquiry-to-approval journey; show synthetic-demo notice; expose Start demo and architecture links; display the supplied bilingual logo without stretching. |
| F02 | Demo scenarios and assets | Seed four deterministic scenarios: mixed-language photo, missing serial, incompatible part, local shortage; derive identifiers from seed 42; validate expected outcomes against generated records. |
| F03 | Demo role switching | Switch the presentation between customer and reviewer using the same anonymous identity and session; authorize review only for enquiries belonging to that active session. |
| F04 | Demo isolation | Bind each session to verified anonymous Supabase identity; check generation and expiry on every read, write and worker completion; exclude demos from operational metrics by default. |
| F05 | Demo reset | Lock session; increment generation; cancel unfinished jobs from prior generation; enqueue Storage cleanup; keep minimal audit; create fresh scenario enquiries on explicit selection. |
| F06 | Responsive layouts | Support 360,768,1280 CSS-pixel widths; stack review panels; horizontally scroll comparison tables within their region; preserve sticky primary review actions without covering content. |
| F07 | Arabic and English interface | Use a locale cookie and complete en/ar message catalogs; persist preference; set document lang and dir; isolate serials, numbers and part identifiers with bdi. |
| F08 | Light and dark themes | Use CSS semantic tokens; initialize from saved preference then system setting; expose accessible toggle; honor reduced motion and browser color-scheme. |
| F09 | Bilingual chat | Accept Arabic, English and mixed text; preserve original message; detect preferred reply locale; render customer messages immediately after successful persistence. |
| F10 | Structured extraction | Extract item descriptions, quantities, urgency and machine hints with strict structured outputs; preserve source spans; missing quantity becomes a clarification rather than assumed order quantity. |
| F11 | Clarifying questions | Use controller reason codes to choose code-owned bilingual questions; persist interrupt; associate answer with item; rerun affected resolution only. |
| F12 | Conversation memory | Persist all messages and typed current state; compact context using retained structured facts; resume by enquiry/revision; never mix customer sessions. |
| F13 | Private uploads | Create pending attachment and unique object path; use signed upload; validate actual bytes and magic type after confirmation; strip EXIF and cap decoded pixels before OCR. |
| F14 | Nameplate OCR | Read validated nameplate via OpenAI vision; return model_text,serial_text,issues and source attachment; persist result only with current lease and revision. |
| F15 | OCR confirmation | Show cropped or original nameplate beside extracted identifiers; require user confirm or correction; record actor and time; preserve leading zeros in serial text. |
| F16 | Photo quality feedback | Check decodability, dimensions and blur heuristic before paid call; return actionable retake instructions; mark heuristic as advisory; allow a readable image despite noncritical blur warning. |
| F17 | Multi-part enquiries | Track up to 20 items with independent quantity, machine, candidate selection and status; clarify individual items; verify aggregate allocation for repeated part requests. |
| F18 | Progress timeline | Show persisted stages, wait reason and last update; poll with bounded backoff; reconnect using server state; separate waiting for customer from waiting for staff. |
| F19 | Enquiry history | Return cursor-paginated owned history with status and created time; filter active demo generation; link to full conversation; use stable created_at/id ordering. |
| F20 | Machine identification | Preserve identify_machine logic for model, serial and rating; return resolved configuration or explicit missing/ambiguous status; normalize numeric serial only after preserving input. |
| F21 | Machine mismatch detection | Compare model and serial together; return mismatch reason with safe next question; prevent retrieval while identity unresolved. |
| F22 | Compatibility gate | Fetch authoritative fitment set first; rank only members; carry source_reference and catalogue version through every candidate. |
| F23 | Aliases and typo matching | Preserve Arabic normalization, part-number keys, phrase scoring and fuzzy token matching; remove machine terms using resolved model context. |
| F24 | Semantic retrieval | Load one BGE-M3 encoder per search process; use normalized 1024-d vectors; retain legacy weighted fusion; fall back to lexical on unavailable embedding path. |
| F25 | Ranked candidates | Return top candidates with lexical/semantic evidence and deterministic tie order; compute runner-up margin before applying response limit. |
| F26 | Ambiguity handling | Use tested score and margin thresholds in code; ask customer to distinguish fuel filter versus separator; allow staff to select only verified candidates. |
| F27 | Match explanations | Show actual alias, machine configuration, supersession chain and fitment reference; derive explanations from search evidence rather than invented model prose. |
| F28 | Compatibility references | Resolve source_reference to version-specific document and page; retain citation with every candidate and approval snapshot. |
| F29 | Evidence page viewer | Authorize assigned reviewer or own demo reviewer; request short-lived worker-signed PDF URL; open exact cited page; label synthetic document. |
| F30 | Old part numbers | Follow supersession chain with cycle protection; display old and current numbers; verify current successor has explicit fitment for resolved configuration. |
| F31 | Candidate comparison | Compare two or three candidates from the same item/revision; show number, names, evidence and warehouse availability; selecting a candidate sends its ID, not browser-authored facts. |
| F32 | Warehouse stock | Show available quantity as on_hand minus reserved; include timestamp and warehouse name; keep display and planner using same snapshot. |
| F33 | Fulfilment planning | Allocate local stock first then reachable warehouses deterministically; compute shortage; use quantity units; do not reserve stock or create orders. |
| F34 | Transfer estimates | Carry integer transfer_days from approved route; show estimate and source warehouse; local availability means zero transfer days. |
| F35 | Stock freshness | Compare stock timestamp with configurable freshness limit; mark stale data in review; re-read current stock during approval; invalidate plan when allocation no longer possible. |
| F36 | Staff inbox | List assigned operational enquiries and own active demo enquiries; filter status,priority,overdue and text; paginate stably; show counts in same access scope. |
| F37 | Review workspace | Assemble current extraction, items, candidates, evidence, stock, draft and timeline; show verification failures; separate staff-only notes from customer messages. |
| F38 | Correct extracted details | Lock enquiry; compare expected revision; apply typed allowed corrections; increment revision; invalidate derived selections/draft/approval; enqueue recomputation; record before and after. |
| F39 | Review actions | Approve only verified current draft; edit prose through controlled schema then reverify; reject with reason; record actor and idempotency key. |
| F40 | Approval invalidation | Bind approval to revision and verified fact hash; any identity,quantity,selection or catalogue-sensitive change requires new draft and approval. |
| F41 | Internal notes | Append reviewer notes with author and timestamp; show only in staff workspace; prohibit customer/PDF exposure; escape rendered content. |
| F42 | Assignments | Admin assigns active reviewer or unassigns; persist assignment history atomically; access changes immediately; demo reviewer access remains session-scoped. |
| F43 | Overdue indicators | Set due_at using configurable urgent/normal thresholds; display overdue only for unresolved states; sort overdue first when requested; store all times UTC. |
| F44 | Conversation summary | Produce staff-only concise summary from authorized messages and confirmed fields; store message IDs and revision; use shared budget wrapper; regenerate on relevant change. |
| F45 | Reply drafting | Generate greeting,explanation and closing as structured slots; code inserts all numbers and allocations; choose Arabic or English from confirmed preference. |
| F46 | Verification gate | Check item/configuration/candidate membership, provenance, catalogue version, selected quantities and allocation bounds; compute canonical fact hash; store named rule results. |
| F47 | Human publication gate | Only approval service inserts recommendation messages; lock enquiry and recheck role,revision and verification; unique publication index prevents duplicates. |
| F48 | Input isolation | Treat customer text,OCR and imported evidence as data; separate trusted instructions; bound tool names,arguments,steps and output size; never execute model-produced templates. |
| F49 | Audit trail | Append actor,request,entity,revision and minimal before/after metadata for AI suggestions and human changes; redact secrets and full sensitive payloads. |
| F50 | Durable workflows | Use Postgres checkpointer and DB event inbox; thread key includes enquiry ID and active revision; serialize processing for one enquiry; recover after restart. |
| F51 | Background jobs | Persist job before Redis dispatch; dispatcher claims by ID; sweeper redispatches pending/expired jobs; worker handles OCR,PDF,imports and cleanup. |
| F52 | Retry and deduplication | Claim with FOR UPDATE SKIP LOCKED; assign lease token; heartbeat; retry transient errors with backoff up to max attempts; fence final writes by lease token. |
| F53 | Graceful failures | Map stable error codes to bilingual recovery guidance; distinguish validation,quota,service outage and staff-required states; preserve user input. |
| F54 | Access and permissions | Verify Supabase issuer,audience,signature,expiry; derive identity server-side; enforce assigned-only review; keep credentials server-side; disable public real-client signup. |
| F55 | Saved machines | Save confirmed model and serial with user label; list own active entries; archive entry; prefill a new enquiry but re-identify against current catalogue. |
| F56 | Repeat enquiry | Copy customer request and confirmed hints into a new enquiry; issue new ID/revision; link origin in audit; run matching,stock and review again. |
| F57 | Catalogue browser | Read published catalogue with model/category/text filters; page results; show part detail and supersession; staff can inspect fitment and sources. |
| F58 | Catalogue imports | Read CSV UTF-8 or XLSX without evaluating formulas; validate row schema,references,serial overlap,supersession cycles and source evidence; show dry-run report; explicit admin publish. |
| F59 | Catalogue versioning | Snapshot validated catalogue canonically; hash records; serialize publication; preserve numeric IDs; atomically retire old version and activate new; invalidate pending enquiries on next action. |
| F60 | Missing-parts queue | Record unresolved item once; allow assigned staff to mark investigating,resolved or unavailable with note; link back to enquiry; no automatic catalogue creation. |
| F61 | Enquiry PDF | Export approved revision only; render logo,bilingual customer text,verified selections,estimates and references; embed Arabic fonts; store private object and signed download. |
| F62 | Labelled evaluations | Include four demos plus Arabic,typo,serial-boundary,ambiguity,stock and injection cases; record expected compatible set and clarification outcome; run deterministic suite without API calls. |
| F63 | Metrics dashboard | Show volume,status,review time,clarification and labelled accuracy with denominators; separate demo traffic; filter time window; scope reviewer data to assignments. |
| F64 | Latency and AI cost | Measure stages with monotonic clock; log model/token usage and estimated cost; reserve confirmed free credit before each attempt; expose consumed/reserved allowance. |
| F65 | Correction feedback | List authorized before/after corrections; let admin curate anonymized labelled eval cases; record reviewer and source revision; never auto-train on unreviewed edits. |
| F66 | Tests and CI | Run service-isolated Python tests,frontend checks,RLS integration and deterministic evals; build images; require explicit environment approval for deployment; pin action SHAs. |
| F67 | Traces | Propagate request/enquiry/job IDs; capture stage timing and safe status; export optional Langfuse traces with payload redaction; operate normally when tracing unavailable. |
| F68 | Recruiter documentation | Write concise overview,real architecture,quick start,demo paths,tests,trade-offs and limitations; link measured evidence; explain deterministic decisions and specialist tools. |
| F69 | Demo walkthrough | Create 3-minute and 8-minute scripts covering happy path,missing serial,incompatibility,stock split and human review; include recording checklist and captions. |
