# Rollback and recovery

Before each implementation prompt, commit a clean checkpoint and record the current schema and catalogue version. Revert only the intended commit after checking later dependencies. Never use a hard reset that discards unrelated work. Reverse applied migrations through tested forward compensating migrations; never reset a shared database.

For deployment, select the previous immutable API and worker image pair compatible with the current schema. Pause new jobs, allow or expire active leases, restart the old pair, and verify readiness before resuming. The web release must match the supported API contract. Rollback must preserve compatibility checks and human approval.

If catalogue activation has not committed, the old pointer remains active. A remote-only version can be reconciled by its hash and count. If an activated version must be reverted, validate the previous snapshot and stock freshness, then make a new audited activation. Historical approvals retain their original facts and evidence.

For reporting failures, retain pending PostgreSQL outbox events and retry with the same event IDs. For uncertain OpenAI completion, retain usage reservations until reconciliation. Redis loss does not remove durable jobs; rate-limited intake fails closed. To recover a lost host, restore the committed Compose configuration and secrets, then recover jobs through their leases. Rehearse restores in development before claiming backup recovery works.
