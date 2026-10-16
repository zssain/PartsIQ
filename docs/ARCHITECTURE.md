# Architecture

## 1. What is in the system?
Next.js customer and staff interfaces on Vercel call a FastAPI gateway behind Caddy on EC2. Supabase Auth establishes identity; PostgreSQL stores authoritative data; Storage holds private photos,evidence and exports. The same EC2 Docker network hosts search,orchestrator,worker,sweeper,orchestrator event consumer and Redis. OpenAI is outbound language/vision; BGE-M3 runs only inside search. Specialists are modules,not independent servers.

## 2. Who owns each responsibility?
| Responsibility | Owner | Exact home |
|---|---|---|
| Auth,demo,customer/staff CRUD | Gateway | services/gateway/app/auth.py,permissions.py,demo.py,enquiries.py,features |
| Identification | Search | services/search/app/identification.py |
| Lexical ranking | Search | services/search/app/lexical.py |
| Retrieval coordination | Search | services/search/app/service.py,repository.py |
| Allocation | Search | services/search/app/fulfilment.py |
| Embedding generation | Search | services/search/app/embedding_ingestion.py |
| Routing and durable state | Orchestrator | services/orchestrator/app/controller.py,graph.py,events.py |
| Intake/parts/reply | Orchestrator specialists | services/orchestrator/app/specialists |
| Verification | Orchestrator | services/orchestrator/app/verification.py |
| Approval/revisions | Orchestrator | services/orchestrator/app/approval.py,revisions.py |
| Nameplate specialist | Worker | services/worker/app/jobs/nameplate.py |
| PDF/signing/cleanup | Worker | services/worker/app/jobs/export_pdf.py,storage.py |
| Imports | Worker and catalogue domain | services/worker/app/features/f58_catalogue_imports.py,tools/catalog/catalog |
| Catalogue publication | Catalogue application | tools/catalog/catalog/versioning.py |
| Shared contracts,audit,credit | Common | libs/partsiq_common/partsiq_common |
| Screens and accessibility | Web | apps/web |
| Schema,RLS and Storage policies | Migrations | supabase/migrations |
| Metrics and corrections API | Gateway | services/gateway/app/features |
| Tests,evaluations and release | Tooling | tests,tools/evals,infra,.github/workflows |

## 3. Why this design?
The controller uses deterministic transitions because missing serials,verification failures and approval gates do not need model routing. Separate specialists give bounded inputs and testable contracts. Compatibility is a database relation,not a similarity judgement. Redis loss is recoverable because job state lives in PostgreSQL. A single host limits operational overhead; it also creates a documented single-host availability limitation. No high-availability claim is made.

## 4. What may touch what?
Web calls gateway and Supabase Auth; it may transfer an authorized private Storage object. Gateway verifies identity,writes intake/session/staff records and calls internal search/orchestrator/worker signing routes. Search reads catalogue and inventory and writes only embeddings through its administrative ingestion entry point. Orchestrator reads/writes workflow data,uses search and OpenAI,and owns final publication. Worker consumes jobs,uses Storage/OpenAI vision,and writes durable workflow events; it never calls orchestrator HTTP. Catalogue publication runs under the restricted catalogue role after validation and admin authorization. Runtime services never use migration credentials.

Within a service: route -> application use case -> domain function -> repository/adapter. Preserve existing legacy modules initially; an abstract layering preference is not permission to rewrite them.

## 5. How does data move?
Gateway commits enquiry,message,revision and start event. Event consumer starts LangGraph. Optional OCR job returns a durable completion event. Customer confirms identifiers. Controller invokes identification and compatible retrieval. Customer/staff resolves ambiguity. Planner computes allocations. Reply specialist fills prose slots; renderer inserts structured facts. Verification records rule results. Staff approves current revision; approval transaction creates one customer recommendation. Export worker renders the approved snapshot. FLOW.md binds these steps to concrete prompt-created functions.

## 6. What cannot break?
Compatible-set membership,explicit evidence,current revision,quantity/stock bounds,assigned/session access,no model writes,no unapproved publication,no stale worker commits,and no paid fallback. CONSTRAINTS.md is the complete rule list.

## 7. Where does new code belong?
Use spec/file-ownership.json as the exhaustive planned application file inventory. A new file must have one creator. Feature backend modules live under the relevant service app/features directory; existing legacy modules retain their paths. UI feature components live in apps/web/components/features. Tests are colocated by service or live in root acceptance/integration directories. Do not introduce another orchestrator,API or catalogue implementation.

## 8. When must the agent ask?
Ask for an unapproved change to locked architecture,permissions,paid services,destructive production migration or safety gates. The specified additions and migrations are already approved. Account IDs,domains and secrets are deployment inputs,not values to invent. Finish local reversible work before reporting an external activation blocker.
