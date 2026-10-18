BEGIN;
ALTER TABLE jobs DROP CONSTRAINT jobs_kind_check;
ALTER TABLE jobs ADD CONSTRAINT jobs_kind_check CHECK(kind IN ('nameplate','export_pdf','catalog_import','catalog_publish','storage_cleanup','workflow','analytics_sync','catalog_sync'));
CREATE TABLE workflow_runs (
 enquiry_id uuid NOT NULL REFERENCES enquiries(id), revision integer NOT NULL CHECK(revision>0),
 step text NOT NULL CHECK(step IN ('intake','await_ocr','confirm','identify','clarify','search','choose','plan','draft','verify','review','complete','needs_staff')),
 state jsonb NOT NULL DEFAULT '{}'::jsonb CHECK(jsonb_typeof(state)='object'),
 lease_token uuid, lease_expires_at timestamptz, updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(enquiry_id,revision), CHECK((lease_token IS NULL)=(lease_expires_at IS NULL))
);
CREATE TABLE workflow_step_results (
 enquiry_id uuid NOT NULL, revision integer NOT NULL, step text NOT NULL,
 input_sha256 text NOT NULL CHECK(input_sha256 ~ '^[a-f0-9]{64}$'),
 output jsonb NOT NULL CHECK(jsonb_typeof(output)='object'), completed_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(enquiry_id,revision,step,input_sha256),
 FOREIGN KEY(enquiry_id,revision) REFERENCES workflow_runs(enquiry_id,revision)
);
CREATE INDEX workflow_runs_lease_idx ON workflow_runs(lease_expires_at) WHERE lease_token IS NOT NULL;
CREATE TABLE catalogue_syncs (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), version_id uuid NOT NULL REFERENCES catalogue_versions(id),
 source text NOT NULL CHECK(source IN ('snowflake','fixture')),
 state text NOT NULL CHECK(state IN ('requested','remote_written','validated','activated','failed')),
 expected_sha256 text NOT NULL CHECK(expected_sha256 ~ '^[a-f0-9]{64}$'),
 observed_sha256 text, record_count integer CHECK(record_count>=0), query_id text,
 error_code text, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(version_id,source)
);
CREATE TABLE analytics_outbox (
 event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), event_type text NOT NULL,
 enquiry_id uuid REFERENCES enquiries(id), revision integer,
 payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
 created_at timestamptz NOT NULL DEFAULT now(), delivered_at timestamptz,
 attempts integer NOT NULL DEFAULT 0 CHECK(attempts>=0), last_error_code text
);
CREATE INDEX analytics_outbox_pending_idx ON analytics_outbox(created_at,event_id) WHERE delivered_at IS NULL;
CREATE TABLE analytics_sync_runs (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), started_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz,
 row_count integer NOT NULL DEFAULT 0 CHECK(row_count>=0),
 state text NOT NULL CHECK(state IN ('running','succeeded','failed')), query_id text, last_error_code text
);
ALTER TABLE workflow_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_step_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE catalogue_syncs ENABLE ROW LEVEL SECURITY;
ALTER TABLE analytics_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE analytics_sync_runs ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON workflow_runs,workflow_step_results,catalogue_syncs,analytics_outbox,analytics_sync_runs FROM PUBLIC,anon,authenticated;
GRANT SELECT ON workflow_runs,workflow_step_results TO partsiq_api;
CREATE POLICY workflow_runs_api_read ON workflow_runs FOR SELECT TO partsiq_api USING(app_private.can_read_enquiry(enquiry_id));
CREATE POLICY workflow_results_api_read ON workflow_step_results FOR SELECT TO partsiq_api USING(app_private.can_read_enquiry(enquiry_id));
GRANT SELECT,INSERT,UPDATE ON workflow_runs,workflow_step_results TO partsiq_workflow;
CREATE POLICY workflow_runs_job ON workflow_runs TO partsiq_workflow USING(true) WITH CHECK(true);
CREATE POLICY workflow_results_job ON workflow_step_results TO partsiq_workflow USING(true) WITH CHECK(true);
GRANT SELECT,INSERT,UPDATE ON catalogue_syncs TO partsiq_catalogue;
CREATE POLICY catalogue_syncs_publisher ON catalogue_syncs TO partsiq_catalogue USING(true) WITH CHECK(true);
GRANT SELECT,INSERT,UPDATE ON analytics_outbox,analytics_sync_runs TO partsiq_worker;
CREATE POLICY analytics_outbox_worker ON analytics_outbox TO partsiq_worker USING(true) WITH CHECK(true);
CREATE POLICY analytics_runs_worker ON analytics_sync_runs TO partsiq_worker USING(true) WITH CHECK(true);
GRANT INSERT ON analytics_outbox TO partsiq_api,partsiq_workflow;
CREATE POLICY analytics_outbox_append ON analytics_outbox FOR INSERT TO partsiq_api,partsiq_workflow WITH CHECK(app_private.can_read_enquiry(enquiry_id));
CREATE TABLE stock_snapshot_receipts (
 id uuid PRIMARY KEY, source text NOT NULL CHECK(source IN ('snowflake','fixture')),
 observed_at timestamptz NOT NULL, activated_at timestamptz NOT NULL DEFAULT now(),
 content_sha256 text NOT NULL CHECK(content_sha256 ~ '^[a-f0-9]{64}$'),
 row_count integer NOT NULL CHECK(row_count>=0), active boolean NOT NULL DEFAULT false
);
CREATE UNIQUE INDEX stock_one_active_idx ON stock_snapshot_receipts((active)) WHERE active;
ALTER TABLE stock_snapshot_receipts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON stock_snapshot_receipts FROM PUBLIC,anon,authenticated;
GRANT SELECT ON stock_snapshot_receipts TO partsiq_api,partsiq_search,partsiq_workflow;
CREATE POLICY stock_snapshot_read ON stock_snapshot_receipts FOR SELECT TO partsiq_api,partsiq_search,partsiq_workflow USING(true);
GRANT SELECT,INSERT,UPDATE ON stock_snapshot_receipts TO partsiq_catalogue;
CREATE POLICY stock_snapshot_publish ON stock_snapshot_receipts TO partsiq_catalogue USING(true) WITH CHECK(true);
COMMIT;
