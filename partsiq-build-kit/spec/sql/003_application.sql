-- Additive application schema. Apply after immutable legacy migrations 001 and 002.
BEGIN;
CREATE SCHEMA IF NOT EXISTS app_private;
REVOKE ALL ON SCHEMA app_private FROM PUBLIC;
CREATE TABLE profiles (
 id uuid PRIMARY KEY REFERENCES auth.users(id),
 display_name text NOT NULL CHECK(length(display_name) BETWEEN 1 AND 120),
 preferred_locale text NOT NULL DEFAULT 'en' CHECK(preferred_locale IN ('en','ar')),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE staff_roles (
 user_id uuid NOT NULL REFERENCES profiles(id),
 role text NOT NULL CHECK(role IN ('reviewer','catalogue_admin','admin')),
 granted_by uuid REFERENCES profiles(id),
 granted_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(user_id,role)
);
CREATE TABLE demo_sessions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 owner_id uuid NOT NULL REFERENCES profiles(id),
 generation integer NOT NULL DEFAULT 1 CHECK(generation>0),
 expires_at timestamptz NOT NULL,
 revoked_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(),
 CHECK(expires_at>created_at)
);
CREATE INDEX demo_sessions_owner_idx ON demo_sessions(owner_id,expires_at DESC);
CREATE TABLE catalogue_versions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 label text NOT NULL UNIQUE,
 state text NOT NULL CHECK(state IN ('staging','published','retired')),
 content_sha256 text NOT NULL CHECK(content_sha256 ~ '^[a-f0-9]{64}$'),
 created_by uuid REFERENCES profiles(id),
 created_at timestamptz NOT NULL DEFAULT now(),
 published_at timestamptz,
 CHECK((state='staging' AND published_at IS NULL) OR (state IN ('published','retired') AND published_at IS NOT NULL))
);
CREATE UNIQUE INDEX catalogue_one_published_idx ON catalogue_versions((state)) WHERE state='published';
CREATE TABLE catalogue_records (
 version_id uuid NOT NULL REFERENCES catalogue_versions(id),
 entity_type text NOT NULL CHECK(entity_type IN ('equipment_families','equipment_models','model_configurations','parts','part_aliases','part_compatibility','part_supersessions','warehouses','warehouse_transfer_routes')),
 entity_key text NOT NULL,
 payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
 PRIMARY KEY(version_id,entity_type,entity_key)
);
CREATE TABLE catalogue_evidence (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 version_id uuid NOT NULL REFERENCES catalogue_versions(id),
 source_reference text NOT NULL CHECK(length(trim(source_reference))>0),
 storage_key text NOT NULL,
 page_number integer NOT NULL CHECK(page_number>0),
 sha256 text NOT NULL CHECK(sha256 ~ '^[a-f0-9]{64}$'),
 synthetic boolean NOT NULL DEFAULT true,
 UNIQUE(version_id,source_reference)
);
ALTER TABLE part_compatibility ADD CONSTRAINT compatibility_nonempty_source CHECK(length(trim(source_reference))>0);
ALTER TABLE part_embeddings ADD COLUMN model_revision text;
ALTER TABLE part_embeddings ADD COLUMN source_sha256 text;
ALTER TABLE enquiries ADD COLUMN owner_id uuid REFERENCES profiles(id);
ALTER TABLE enquiries ADD COLUMN session_id uuid REFERENCES demo_sessions(id);
ALTER TABLE enquiries ADD COLUMN session_generation integer;
ALTER TABLE enquiries ADD COLUMN revision integer NOT NULL DEFAULT 1 CHECK(revision>0);
ALTER TABLE enquiries ADD COLUMN catalogue_version_id uuid REFERENCES catalogue_versions(id);
ALTER TABLE enquiries ADD COLUMN destination_warehouse_id smallint REFERENCES warehouses(id);
ALTER TABLE enquiries ADD COLUMN assigned_to uuid REFERENCES profiles(id);
ALTER TABLE enquiries ADD COLUMN priority text NOT NULL DEFAULT 'normal' CHECK(priority IN ('normal','urgent'));
ALTER TABLE enquiries ADD COLUMN due_at timestamptz;
ALTER TABLE enquiries ADD COLUMN idempotency_key uuid;
ALTER TABLE enquiries ADD CONSTRAINT enquiry_demo_pair CHECK((session_id IS NULL AND session_generation IS NULL) OR (session_id IS NOT NULL AND session_generation>0));
CREATE UNIQUE INDEX enquiries_owner_idempotency_idx ON enquiries(owner_id,idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX enquiries_owner_created_idx ON enquiries(owner_id,created_at DESC,id);
CREATE INDEX enquiries_assigned_status_idx ON enquiries(assigned_to,status,created_at DESC,id);
CREATE INDEX enquiries_demo_idx ON enquiries(session_id,session_generation);
CREATE TABLE enquiry_items (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 enquiry_id uuid NOT NULL REFERENCES enquiries(id),
 ordinal smallint NOT NULL CHECK(ordinal BETWEEN 1 AND 20),
 requested_text text NOT NULL CHECK(length(trim(requested_text))>0),
 quantity numeric(10,3) NOT NULL CHECK(quantity>0 AND quantity<=100000),
 model_text text,
 serial_text text,
 configuration_id integer REFERENCES model_configurations(id),
 selected_part_id integer REFERENCES parts(id),
 status text NOT NULL DEFAULT 'unresolved' CHECK(status IN ('unresolved','needs_information','ready','unavailable')),
 revision integer NOT NULL CHECK(revision>0),
 UNIQUE(enquiry_id,ordinal),
 UNIQUE(enquiry_id,id)
);
ALTER TABLE enquiry_candidates ADD COLUMN item_id uuid;
ALTER TABLE enquiry_candidates ADD COLUMN revision integer NOT NULL DEFAULT 1;
ALTER TABLE enquiry_candidates ADD COLUMN catalogue_version_id uuid REFERENCES catalogue_versions(id);
ALTER TABLE enquiry_candidates ADD COLUMN evidence_id uuid REFERENCES catalogue_evidence(id);
ALTER TABLE enquiry_candidates DROP CONSTRAINT enquiry_candidates_pkey;
ALTER TABLE enquiry_candidates DROP CONSTRAINT enquiry_candidates_enquiry_id_part_id_key;
-- Historical rows receive a legacy item before the new per-item keys are enforced.
INSERT INTO enquiry_items(enquiry_id,ordinal,requested_text,quantity,revision)
 SELECT id,1,CASE WHEN length(trim(raw_text))>0 THEN raw_text ELSE 'Historical enquiry' END,1,revision FROM enquiries;
UPDATE enquiry_candidates c SET item_id=i.id FROM enquiry_items i WHERE i.enquiry_id=c.enquiry_id AND i.ordinal=1;
ALTER TABLE enquiry_candidates ALTER COLUMN item_id SET NOT NULL;
ALTER TABLE enquiry_candidates ADD CONSTRAINT candidate_item_fk FOREIGN KEY(enquiry_id,item_id) REFERENCES enquiry_items(enquiry_id,id);
ALTER TABLE enquiry_candidates ADD PRIMARY KEY(item_id,revision,rank);
ALTER TABLE enquiry_candidates ADD UNIQUE(item_id,revision,part_id);
ALTER TABLE enquiry_attachments ADD COLUMN status text NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','validated','rejected','deleted'));
ALTER TABLE enquiry_attachments ADD COLUMN sha256 text;
ALTER TABLE enquiry_attachments ADD COLUMN revision integer NOT NULL DEFAULT 1;
CREATE TABLE messages (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 enquiry_id uuid NOT NULL REFERENCES enquiries(id),
 revision integer NOT NULL CHECK(revision>0),
 kind text NOT NULL CHECK(kind IN ('customer','clarification','status','recommendation')),
 body text NOT NULL CHECK(length(body) BETWEEN 1 AND 12000),
 author_id uuid REFERENCES profiles(id),
 decision_id uuid REFERENCES review_decisions(id),
 idempotency_key uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(enquiry_id,idempotency_key),
 CHECK((kind='recommendation' AND decision_id IS NOT NULL) OR (kind<>'recommendation' AND decision_id IS NULL))
);
CREATE UNIQUE INDEX messages_one_publication_idx ON messages(enquiry_id,revision) WHERE kind='recommendation';
CREATE INDEX messages_enquiry_created_idx ON messages(enquiry_id,created_at,id);
CREATE TABLE enquiry_revisions (
 enquiry_id uuid NOT NULL REFERENCES enquiries(id),
 revision integer NOT NULL CHECK(revision>0),
 snapshot jsonb NOT NULL CHECK(jsonb_typeof(snapshot)='object'),
 changed_by uuid REFERENCES profiles(id),
 reason text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(enquiry_id,revision)
);
CREATE TABLE extractions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 enquiry_id uuid NOT NULL REFERENCES enquiries(id),
 attachment_id uuid REFERENCES enquiry_attachments(id),
 revision integer NOT NULL,
 model_text text,
 serial_text text,
 issues jsonb NOT NULL DEFAULT '[]' CHECK(jsonb_typeof(issues)='array'),
 confirmed_by uuid REFERENCES profiles(id),
 confirmed_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(),
 CHECK((confirmed_by IS NULL)=(confirmed_at IS NULL))
);
CREATE INDEX extractions_enquiry_idx ON extractions(enquiry_id,revision);
CREATE TABLE fulfilment_plans (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 enquiry_id uuid NOT NULL REFERENCES enquiries(id),
 revision integer NOT NULL,
 item_id uuid NOT NULL,
 requested_quantity numeric(10,3) NOT NULL CHECK(requested_quantity>0),
 allocations jsonb NOT NULL CHECK(jsonb_typeof(allocations)='array'),
 shortage numeric(10,3) NOT NULL CHECK(shortage>=0),
 stock_snapshot jsonb NOT NULL CHECK(jsonb_typeof(stock_snapshot)='array'),
 calculated_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(enquiry_id,item_id) REFERENCES enquiry_items(enquiry_id,id),
 UNIQUE(item_id,revision)
);
CREATE TABLE drafts (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 enquiry_id uuid NOT NULL REFERENCES enquiries(id),
 revision integer NOT NULL,
 locale text NOT NULL CHECK(locale IN ('en','ar')),
 prose jsonb NOT NULL CHECK(jsonb_typeof(prose)='object'),
 verified_facts jsonb NOT NULL CHECK(jsonb_typeof(verified_facts)='object'),
 rendered_text text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(enquiry_id,revision)
);
CREATE TABLE verification_results (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 enquiry_id uuid NOT NULL REFERENCES enquiries(id),
 revision integer NOT NULL,
 draft_id uuid NOT NULL REFERENCES drafts(id),
 passed boolean NOT NULL,
 failures jsonb NOT NULL CHECK(jsonb_typeof(failures)='array'),
 facts_sha256 text NOT NULL CHECK(facts_sha256 ~ '^[a-f0-9]{64}$'),
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(enquiry_id,revision)
);
ALTER TABLE review_decisions ADD COLUMN revision integer NOT NULL DEFAULT 1;
ALTER TABLE review_decisions ADD COLUMN reviewer_id uuid REFERENCES profiles(id);
ALTER TABLE review_decisions ADD COLUMN verification_id uuid REFERENCES verification_results(id);
ALTER TABLE review_decisions ADD COLUMN idempotency_key uuid;
CREATE UNIQUE INDEX review_decisions_idempotency_idx ON review_decisions(enquiry_id,idempotency_key) WHERE idempotency_key IS NOT NULL;
ALTER TABLE review_approved_parts ADD COLUMN item_id uuid REFERENCES enquiry_items(id);
CREATE TABLE internal_notes (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), enquiry_id uuid NOT NULL REFERENCES enquiries(id),
 author_id uuid NOT NULL REFERENCES profiles(id), body text NOT NULL CHECK(length(trim(body)) BETWEEN 1 AND 4000),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX internal_notes_enquiry_idx ON internal_notes(enquiry_id,created_at,id);
CREATE TABLE assignment_events (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), enquiry_id uuid NOT NULL REFERENCES enquiries(id),
 assigned_to uuid REFERENCES profiles(id), assigned_by uuid NOT NULL REFERENCES profiles(id),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE saved_machines (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), owner_id uuid NOT NULL REFERENCES profiles(id),
 session_id uuid REFERENCES demo_sessions(id), session_generation integer,
 label text NOT NULL CHECK(length(trim(label)) BETWEEN 1 AND 120),
 model_id integer NOT NULL REFERENCES equipment_models(id), serial_text text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), archived_at timestamptz,
 CHECK((session_id IS NULL AND session_generation IS NULL) OR (session_id IS NOT NULL AND session_generation>0))
);
CREATE INDEX saved_machines_owner_idx ON saved_machines(owner_id,created_at DESC);
CREATE TABLE missing_part_requests (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), enquiry_id uuid NOT NULL REFERENCES enquiries(id),
 item_id uuid NOT NULL, status text NOT NULL DEFAULT 'open' CHECK(status IN ('open','investigating','resolved','unavailable')),
 staff_note text NOT NULL DEFAULT '', resolved_by uuid REFERENCES profiles(id),
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(enquiry_id,item_id) REFERENCES enquiry_items(enquiry_id,id), UNIQUE(item_id)
);
CREATE TABLE jobs (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), enquiry_id uuid REFERENCES enquiries(id),
 revision integer, session_generation integer,
 kind text NOT NULL CHECK(kind IN ('nameplate','export_pdf','catalog_import','catalog_publish','storage_cleanup')),
 status text NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','running','succeeded','failed','cancelled')),
 payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
 result jsonb, dedupe_key text NOT NULL UNIQUE,
 attempts integer NOT NULL DEFAULT 0 CHECK(attempts>=0), max_attempts integer NOT NULL DEFAULT 3 CHECK(max_attempts BETWEEN 1 AND 5),
 available_at timestamptz NOT NULL DEFAULT now(), lease_token uuid, lease_expires_at timestamptz,
 last_error_code text, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 CHECK((status='running' AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL) OR status<>'running')
);
CREATE INDEX jobs_claim_idx ON jobs(status,available_at,lease_expires_at);
CREATE TABLE workflow_events (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), enquiry_id uuid NOT NULL REFERENCES enquiries(id), revision integer NOT NULL,
 kind text NOT NULL CHECK(kind IN ('start','message','ocr_completed','approved','retry')),
 payload jsonb NOT NULL DEFAULT '{}', dedupe_key text NOT NULL UNIQUE,
 processed_at timestamptz, lease_token uuid, lease_expires_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX workflow_events_pending_idx ON workflow_events(created_at) WHERE processed_at IS NULL;
CREATE TABLE exports (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), enquiry_id uuid NOT NULL REFERENCES enquiries(id),
 revision integer NOT NULL, decision_id uuid NOT NULL REFERENCES review_decisions(id),
 job_id uuid NOT NULL REFERENCES jobs(id), storage_key text UNIQUE, sha256 text,
 status text NOT NULL CHECK(status IN ('pending','ready','failed','deleted')),
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(enquiry_id,revision)
);
CREATE TABLE import_batches (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), created_by uuid NOT NULL REFERENCES profiles(id),
 version_id uuid REFERENCES catalogue_versions(id), job_id uuid REFERENCES jobs(id),
 storage_key text NOT NULL, sha256 text NOT NULL, status text NOT NULL CHECK(status IN ('uploaded','validating','invalid','valid','published')),
 row_count integer NOT NULL DEFAULT 0 CHECK(row_count BETWEEN 0 AND 50000),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE import_rows (
 batch_id uuid NOT NULL REFERENCES import_batches(id), row_number integer NOT NULL CHECK(row_number>0),
 entity_type text NOT NULL, payload jsonb NOT NULL, errors jsonb NOT NULL DEFAULT '[]',
 PRIMARY KEY(batch_id,row_number)
);
CREATE TABLE ai_budget_accounts (
 id text PRIMARY KEY, cap_usd numeric(14,8) NOT NULL CHECK(cap_usd>=0),
 reserved_usd numeric(14,8) NOT NULL DEFAULT 0 CHECK(reserved_usd>=0),
 consumed_usd numeric(14,8) NOT NULL DEFAULT 0 CHECK(consumed_usd>=0),
 expires_at timestamptz NOT NULL, enabled boolean NOT NULL DEFAULT false,
 CHECK(reserved_usd+consumed_usd<=cap_usd)
);
CREATE TABLE ai_usage (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), enquiry_id uuid REFERENCES enquiries(id),
 request_key uuid NOT NULL UNIQUE, budget_account_id text NOT NULL REFERENCES ai_budget_accounts(id),
 model text NOT NULL, stage text NOT NULL, status text NOT NULL CHECK(status IN ('reserved','completed','uncertain','released')),
 reserved_usd numeric(14,8) NOT NULL CHECK(reserved_usd>=0), actual_usd numeric(14,8) CHECK(actual_usd>=0),
 input_tokens integer CHECK(input_tokens>=0), output_tokens integer CHECK(output_tokens>=0),
 duration_ms integer CHECK(duration_ms>=0), provider_request_id text,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ai_usage_created_idx ON ai_usage(created_at,stage);
CREATE TABLE eval_cases (
 id text PRIMARY KEY, scenario text NOT NULL, input jsonb NOT NULL, expected jsonb NOT NULL,
 catalogue_version_id uuid NOT NULL REFERENCES catalogue_versions(id),
 language text NOT NULL CHECK(language IN ('en','ar','mixed')), approved_by uuid REFERENCES profiles(id)
);
CREATE TABLE eval_runs (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), git_sha text NOT NULL, model text NOT NULL,
 dataset_sha256 text NOT NULL, started_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz,
 status text NOT NULL CHECK(status IN ('running','passed','failed'))
);
CREATE TABLE eval_results (
 run_id uuid NOT NULL REFERENCES eval_runs(id), case_id text NOT NULL REFERENCES eval_cases(id),
 actual jsonb NOT NULL, passed boolean NOT NULL, duration_ms integer NOT NULL CHECK(duration_ms>=0),
 PRIMARY KEY(run_id,case_id)
);
CREATE TABLE correction_records (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), enquiry_id uuid NOT NULL REFERENCES enquiries(id),
 revision integer NOT NULL, corrected_by uuid NOT NULL REFERENCES profiles(id),
 before_value jsonb NOT NULL, after_value jsonb NOT NULL, reason text NOT NULL,
 eval_case_id text REFERENCES eval_cases(id), created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE enquiry_summaries (
 enquiry_id uuid NOT NULL REFERENCES enquiries(id), revision integer NOT NULL,
 summary text NOT NULL, source_message_ids uuid[] NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(enquiry_id,revision)
);
CREATE TABLE retention_policies (
 scope text PRIMARY KEY CHECK(scope IN ('demo','client')),
 enquiry_days integer CHECK(enquiry_days BETWEEN 1 AND 3650),
 upload_days integer CHECK(upload_days BETWEEN 1 AND 3650),
 audit_days integer CHECK(audit_days BETWEEN 1 AND 3650),
 configured_by uuid REFERENCES profiles(id), configured_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO retention_policies(scope,enquiry_days,upload_days,audit_days) VALUES ('demo',1,1,NULL),('client',NULL,NULL,NULL);
-- NULL client values disable live-client onboarding, not indefinite silent consent.
ALTER TABLE audit_log ADD COLUMN enquiry_id uuid REFERENCES enquiries(id);
ALTER TABLE audit_log ADD COLUMN revision integer;
CREATE INDEX audit_log_enquiry_idx ON audit_log(enquiry_id,occurred_at DESC);
CREATE FUNCTION app_private.lock_supersessions() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN PERFORM pg_advisory_xact_lock(710069); RETURN NEW; END; $$;
CREATE TRIGGER aa_supersessions_lock BEFORE INSERT OR UPDATE ON part_supersessions FOR EACH ROW EXECUTE FUNCTION app_private.lock_supersessions();
CREATE FUNCTION app_private.immutable_record() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'immutable historical record' USING ERRCODE='42501'; END; $$;
CREATE TRIGGER catalogue_records_immutable BEFORE UPDATE OR DELETE ON catalogue_records FOR EACH ROW EXECUTE FUNCTION app_private.immutable_record();
CREATE TRIGGER revisions_immutable BEFORE UPDATE OR DELETE ON enquiry_revisions FOR EACH ROW EXECUTE FUNCTION app_private.immutable_record();
CREATE TABLE idempotency_records (
 actor_id uuid NOT NULL REFERENCES profiles(id),
 operation text NOT NULL,
 key uuid NOT NULL,
 request_sha256 text NOT NULL CHECK(request_sha256 ~ '^[a-f0-9]{64}$'),
 response jsonb,
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(actor_id,operation,key)
);
COMMIT;
