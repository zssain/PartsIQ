# Decision record

All entries below reflect the owner's approval in the planning conversation on 2026-10-11. Authoring model identifier was not exposed; no invented model version is recorded.

| ADR | Decision | Reason and consequence |
|---|---|---|
| ADR-001 | Extend legacy backend | Preserve existing modules,tables,numeric IDs and characterizations; additive migrations only except explicitly approved candidate key upgrade |
| ADR-002 | EC2 Compose behind Caddy | One host,low operational complexity; conditional AWS Free Plan,local fallback; Render alternative only |
| ADR-003 | Deterministic LangGraph controller | No LLM supervisor for rule-based transitions |
| ADR-004 | Supabase dev/prod plus Vercel | Separate projects and secrets; preview never points at prod |
| ADR-005 | OpenAI language/vision | Owner has keys/free credits; retain provider; no Gemini change |
| ADR-006 | Search-only BGE-M3 | One encoder instance; tools submit embedding work |
| ADR-007 | Structured facts and code renderer | LLM prose cannot authorize part numbers,quantities or delivery claims |
| ADR-008 | Human approval bound to revision | Edits/catalogue changes invalidate pending derived results |
| ADR-009 | Durable jobs/events and lease fencing | Redis dispatch is recoverable; no exactly-once external-call guarantee |
| ADR-010 | 69 grouped features | Combine scenarios/photos and access/roles; preserve all selected behaviours |
| ADR-011 | Foundation ownership plus F coverage prompts | 69 trace files; no duplicate implementation for covered features |
| ADR-012 | Public synthetic demo; real signup disabled | Recruiter-first scope; assigned-only operational review |
| ADR-013 | Mandatory OCR confirmation | Do not treat model confidence as calibrated correctness |
| ADR-014 | Worker Storage capability | Private worker credential only for authorized object operations; gateway uses end-user upload policy |
| ADR-015 | Application free-credit allowance | Default disabled; manually confirm allowance/expiry; hard local reserve; no automatic paid fallback |
| ADR-016 | Client-defined retention | Demo default24h; real-client onboarding blocked until policy configured |
| ADR-017 | Preserve weighted ranking | No unapproved RRF/trigram rewrite; characterize then evaluate changes |
| ADR-018 | Supersession integrity correction | Terminal current part needs explicit fitment; calculate confidence margin before truncation |
| ADR-019 | Supabase SSR0.8.0 | Replaces proposed0.12.7 because it required supabase-js2.114.0; matched pair resolves with client2.99.1 |
| ADR-020 | Brand source preserved | Navy/gold tokens; supplied PNG artwork; licensed Noto fonts; no fabricated SVG |

## 2026-10-17 — Owner-requested UI revamp
Owner asked to revamp the entire interface using the supplied PartsIQ workspace, Visentix and Teclusion references, including foil parallax and branding. Implement within the existing Next.js/Vercel application, not a new hosted Site or service. Preserve supplied logo, package pins, domain APIs and human approval gates. Use CSS material effects and existing lucide-react icons; no animation dependency or remote assets. PartsIQ reference CSS and Visentix public CSS were inspected; Teclusion timed out. Existing frontend implementation sequence is complete according to HANDOVER; this is one additional presentation task. Rollback: revert this task commit; pre-task tag `pre-ui-revamp`.
