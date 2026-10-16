# Rollback

## Code
One commit per prompt. Tag pre-ID before work. Inspect the commit hash and diff before reverting. `git revert --no-edit HEAD` is valid only when HEAD is the intended task; otherwise use the verified task hash. Never hard-reset unrelated changes. Rerun affected feature tests and update handover.

## Database
Never edit applied migrations. Take an authorized export/backup before production schema changes. Prefer forward repair/additive compatibility migration. Candidate key migration preserves historical rows by creating item records. Its reversal requires proving no multi-item records would be lost; otherwise do not reverse. Restore only into an isolated recovery database first,compare receipts and obtain operator approval before replacing live state. Audit history is not deleted as routine rollback.

## Catalogue
Publication is a transaction. Invalid batch never becomes active. To restore a prior catalogue,create a new validated publication from its immutable records,retain history and invalidate pending recommendations. Do not rewrite old version rows or pretend prior approvals used the new version.

## Deployment
Retain previous release's image digests and environment schema. On failed healthcheck,switch to previous schema-compatible images. If current migration is not backward compatible,halt and follow the migration-specific recovery plan. Preserve logs and current DB state; do not reset volumes. Free-credit expiry disables live AI and triggers local/recorded-demo fallback,not paid upgrade.

## Demo reset
Reset is deliberate expiry of a generation; it is not an audit rollback. Old jobs are cancelled/fenced. Storage cleanup is asynchronous and retryable. The user starts a new scenario rather than resurrecting obsolete processing results.
