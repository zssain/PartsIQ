-- Additive: durable state for the workspace runtime (ADR 0002 database mode).
-- Apply after 20261020000100_agent_collaboration.sql. Nothing existing is altered or dropped;
-- new columns are nullable or defaulted so existing rows stay valid.
BEGIN;

-- Enquiry-level runtime state that has no dedicated column in the 003 schema.
ALTER TABLE enquiries ADD COLUMN IF NOT EXISTS locale text CHECK (locale IS NULL OR locale IN ('en','ar'));
ALTER TABLE enquiries ADD COLUMN IF NOT EXISTS run_mode text CHECK (run_mode IS NULL OR run_mode IN ('guided','collaboration'));
ALTER TABLE enquiries ADD COLUMN IF NOT EXISTS current_run_id uuid REFERENCES workflow_runs(id);
-- Derived, revision-bound state (progress events, pending question, nameplate reading, instructions,
-- verified facts/evidence used by the deterministic gate). Rebuilt on every revision.
ALTER TABLE enquiries ADD COLUMN IF NOT EXISTS workspace_state jsonb NOT NULL DEFAULT '{}'::jsonb
 CHECK (jsonb_typeof(workspace_state) = 'object' AND octet_length(workspace_state::text) <= 262144);

-- Per-item derived detail (candidates with scores/sources, plan lines, notes) beside the typed columns.
ALTER TABLE enquiry_items ADD COLUMN IF NOT EXISTS detail jsonb NOT NULL DEFAULT '{}'::jsonb
 CHECK (jsonb_typeof(detail) = 'object' AND octet_length(detail::text) <= 65536);

-- Collaboration controller state needed to resume a run without repeating committed turns.
ALTER TABLE workflow_runs ADD COLUMN IF NOT EXISTS agenda jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(agenda) = 'array');
ALTER TABLE workflow_runs ADD COLUMN IF NOT EXISTS board jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(board) = 'object');
ALTER TABLE workflow_runs ADD COLUMN IF NOT EXISTS seen_signatures text[] NOT NULL DEFAULT '{}';
ALTER TABLE workflow_runs ADD COLUMN IF NOT EXISTS next_seq integer NOT NULL DEFAULT 1 CHECK (next_seq > 0);
ALTER TABLE workflow_runs ADD COLUMN IF NOT EXISTS current_step text;

-- Import batch dry-run report and preview (the 003 table holds file + status only).
ALTER TABLE import_batches ADD COLUMN IF NOT EXISTS filename text;
ALTER TABLE import_batches ADD COLUMN IF NOT EXISTS detail jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(detail) = 'object');
ALTER TABLE import_batches ADD COLUMN IF NOT EXISTS base_version_id uuid REFERENCES catalogue_versions(id);

-- Saved machines keep the identifiers exactly as the customer typed them.
ALTER TABLE saved_machines ADD COLUMN IF NOT EXISTS model_text text;

-- Pending-action ordering for one enquiry across revisions.
CREATE INDEX IF NOT EXISTS workflow_runs_status_lease_idx ON workflow_runs (status) WHERE status IN ('queued','running','pausing');
CREATE INDEX IF NOT EXISTS enquiries_session_null_idx ON enquiries (created_at DESC) WHERE session_id IS NULL;

-- Durable job dispatch for the worker also covers workflow runs and evaluations (additive: the
-- original constraint only listed nameplate/export/catalogue/cleanup kinds).
ALTER TABLE jobs DROP CONSTRAINT IF EXISTS jobs_kind_check;
ALTER TABLE jobs ADD CONSTRAINT jobs_kind_check CHECK (kind IN ('nameplate','export_pdf','catalog_import','catalog_publish','storage_cleanup','workflow','evaluation'));

-- Reviewer corrections keep their review state (only reviewed corrections may become eval cases).
ALTER TABLE correction_records ADD COLUMN IF NOT EXISTS field text;
ALTER TABLE correction_records ADD COLUMN IF NOT EXISTS reviewed boolean NOT NULL DEFAULT false;

-- Idempotency for workspace operations keyed by operation scope + client key (the 003
-- idempotency_records table stays the actor-scoped store for enquiry intake).
CREATE TABLE IF NOT EXISTS workspace_idempotency (
 scope text NOT NULL CHECK (length(scope) BETWEEN 1 AND 40),
 key uuid NOT NULL,
 request_sha256 text NOT NULL,
 response jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY (scope, key)
);
ALTER TABLE workspace_idempotency ENABLE ROW LEVEL SECURITY;

COMMIT;
