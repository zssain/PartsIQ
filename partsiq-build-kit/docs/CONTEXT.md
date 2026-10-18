# Project context

Mohammed Zuhair Hussain is building a recruiter-facing spare-parts enquiry application inspired by industrial equipment distribution in Saudi Arabia. The demonstration uses synthetic equipment, parts, stock and customers; it does not represent a commercial relationship or real TAMGO inventory. The project should demonstrate full-stack engineering, bilingual AI extraction, deterministic data validation, warehouse planning, REST API design, data-platform integration and human review.

The original journey is retained: a Riyadh customer sends Arabic/English text and a nameplate photo; the system extracts details, confirms identifiers, identifies the machine, filters compatible parts, asks about ambiguity, plans available quantities, drafts a reply, and pauses for staff approval. Staff corrections are auditable and can support reviewed evaluation cases.

The earlier multi-agent implementation plan was explicitly replaced on16 October 2026. All 69 feature groups remain. Application orchestration now means ordinary Python functions and a persisted finite-state workflow. There are no specialist agents and no model-selected next steps. AGENTS.md describes how an external coding assistant should work on the repository, not runtime agents.

Snowflake was requested as the data-platform addition. Adopted design: immutable catalogue source versions and redacted analytical events in Snowflake; operational records, auth, files and validated relational serving cache in Supabase. This preserves PostgreSQL compatibility constraints and avoids expensive warehouse queries on every chat poll. Feature behavior must be identical between a validated live snapshot and an explicitly selected synthetic fixture snapshot, apart from provenance and freshness indicators.

Budget remains zero paid spend. The owner says they have free OpenAI keys, but provider allowance and expiry still require confirmation. Snowflake trial availability cannot be assumed permanent. Live services are disabled by default. Fixture mode must never be presented as a successful live Snowflake/OpenAI integration test.
