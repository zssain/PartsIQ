-- Run after library saver setup,never within its concurrent-index transaction.
BEGIN;
REVOKE ALL ON SCHEMA checkpoints FROM PUBLIC,anon,authenticated;
GRANT USAGE ON SCHEMA checkpoints TO partsiq_orchestrator;
GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA checkpoints TO partsiq_orchestrator;
ALTER TABLE checkpoints.checkpoint_migrations ENABLE ROW LEVEL SECURITY;
ALTER TABLE checkpoints.checkpoints ENABLE ROW LEVEL SECURITY;
ALTER TABLE checkpoints.checkpoint_blobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE checkpoints.checkpoint_writes ENABLE ROW LEVEL SECURITY;
CREATE POLICY checkpoints_migration_read ON checkpoints.checkpoint_migrations FOR SELECT TO partsiq_orchestrator USING(true);
CREATE POLICY checkpoints_state_runtime ON checkpoints.checkpoints TO partsiq_orchestrator USING(true) WITH CHECK(true);
CREATE POLICY checkpoints_blobs_runtime ON checkpoints.checkpoint_blobs TO partsiq_orchestrator USING(true) WITH CHECK(true);
CREATE POLICY checkpoints_writes_runtime ON checkpoints.checkpoint_writes TO partsiq_orchestrator USING(true) WITH CHECK(true);
REVOKE INSERT,UPDATE,DELETE ON checkpoints.checkpoint_migrations FROM partsiq_orchestrator;
COMMIT;
