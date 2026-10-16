# Constraints

1. Next.js runs on Vercel; Supabase owns data,Auth and private files in separate dev/prod projects.
2. Production backend is one EC2 host with Docker Compose,Caddy,gateway,search,orchestrator,worker,sweeper and Redis. Render is an alternative appendix only.
3. OpenAI language and vision only. Use the owner's key after explicit credit allowance configuration. No Gemini switch or paid fallback.
4. BGE-M3 loads only in search. Catalogue tools and workers submit embedding work to search.
5. Compatibility,quantity validation,stock planning,verification,workflow transitions and approval live in code. Models can extract customer statements and propose prose,not authorize facts.
6. Specialist tools are read-only. A deterministic application layer persists validated results. An LLM never receives a write,approval or catalogue-publication tool.
7. Final recommendations require current-revision human approval. Customer messages,code-owned clarification and safe progress messages do not require recommendation approval.
8. Only orchestrator approval code publishes recommendation messages; database trigger and unique publication index backstop it.
9. Assigned-only staff access for real enquiries; own active demo session for demo review. Admin assignment is audited.
10. No secret in frontend,NEXT_PUBLIC variables,URLs,logs,fixtures,trace payloads or commits. Publishable Supabase key is not a secret.
11. Runtime SQL uses separate restricted service login roles. Gateway sets transaction-local verified actor context. Browser does not query application tables directly.
12. Private Storage transfer is the narrow browser exception. Gateway authorizes; signed links expire; worker storage credential is never used for application-table REST access.
13. Public containers: Caddy80/443 only. Internal service token and request ID required; do not expose search,Redis,worker or orchestrator.
14. Redis is dispatch/cache,not durable truth. Jobs,events and workflow checkpoints survive Redis loss.
15. A stale revision,session generation or lease token cannot commit derived results. Approval is transactional and idempotent.
16. Preserve legacy modules,numeric IDs,weighted lexical/semantic ranking and transfer_days unless a separately approved ADR changes them.
17. Published evidence/revision snapshots are immutable. Audit is append-only for application roles; database-owner access is not magically prevented.
18. No voice,quotation builder,prices,payments,external messaging,actual stock reservations,ERP sync or order creation.
19. No unapproved dependency,folder pattern or service. Exact direct pins and transitive lock references are supplied; verify again when executing on the target runtime.
20. Do not edit applied migrations or reset production. Preview/local uses dev or disposable Supabase only.
21. Production client retention must be configured before real-client onboarding. Public V1 uses synthetic demo data.
22. No fake accuracy,latency,uptime,client affiliation,test result or deployed-status claim. Measured evidence must name dataset and environment.
