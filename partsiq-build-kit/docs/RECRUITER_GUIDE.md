# Recruiter project explanation

PartsIQ is a bilingual spare-parts enquiry platform. OpenAI extracts customer text and nameplate details. Python identifies equipment, filters compatible parts, plans warehouse quantities and validates the reply. Staff approve the final recommendation. Snowflake supplies versioned catalogue data and redacted reporting; Supabase provides transactional records, authentication and private files.

The engineering story is the boundary between probabilistic extraction and deterministic decisions. Demonstrate serial-range constraints, compatibility before ranking, revision-bound approval, job leases, idempotent REST writes and recoverable Snowflake synchronization. Explain why interactive requests use a validated relational cache and why Snowflake source constraints are validated explicitly.

Do not describe this as a multi-agent system or claim real distributor adoption without evidence. Add repository, deployed application, test receipts and recorded walkthrough links only when they exist. A fixture deployment demonstrates application behavior but must be labelled separately from live provider integration evidence.
