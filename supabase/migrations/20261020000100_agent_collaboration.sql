-- Additive: durable workflow runs, agent exchanges, user commands and pending actions (ADR 0002).
-- Apply after 20261011000500_storage.sql. Nothing existing is altered or dropped.
-- Runtime roles get SELECT/INSERT/UPDATE on runs + pending (state transitions) and INSERT/SELECT
-- only on the append-only exchange and command logs.
BEGIN;

CREATE TABLE workflow_runs (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 enquiry_id uuid NOT NULL REFERENCES enquiries(id),
 revision integer NOT NULL CHECK (revision > 0),
 mode text NOT NULL CHECK (mode IN ('guided','collaboration')),
 status text NOT NULL CHECK (status IN ('queued','running','pausing','paused','waiting_user','waiting_consent','blocked','awaiting_review','completed','cancelled','failed','superseded','needs_staff')),
 control text NOT NULL DEFAULT 'active' CHECK (control IN ('active','pause_requested','paused','cancel_requested','cancelled')),
 execution_source text NOT NULL CHECK (execution_source IN ('fixture','live')),
 created_by uuid NOT NULL REFERENCES profiles(id),
 catalogue_version_id uuid NOT NULL REFERENCES catalogue_versions(id),
 session_id uuid REFERENCES demo_sessions(id),
 session_generation integer,
 limits jsonb NOT NULL CHECK (jsonb_typeof(limits) = 'object'),
 agent_turns integer NOT NULL DEFAULT 0 CHECK (agent_turns >= 0),
 tool_calls integer NOT NULL DEFAULT 0 CHECK (tool_calls >= 0),
 input_tokens integer NOT NULL DEFAULT 0 CHECK (input_tokens >= 0),
 output_tokens integer NOT NULL DEFAULT 0 CHECK (output_tokens >= 0),
 estimated_usd numeric(12,6) NOT NULL DEFAULT 0 CHECK (estimated_usd >= 0),
 retries integer NOT NULL DEFAULT 0 CHECK (retries >= 0),
 active_seconds numeric(10,2) NOT NULL DEFAULT 0 CHECK (active_seconds >= 0),
 state_version integer NOT NULL DEFAULT 1 CHECK (state_version > 0),
 -- Bumped on cancel/supersede/reset; a worker commits a step only while its captured fence holds.
 fence integer NOT NULL DEFAULT 0 CHECK (fence >= 0),
 lease_token uuid,
 lease_expires_at timestamptz,
 thread_id text,
 carried_from uuid REFERENCES workflow_runs(id),
 blocked_reason text,
 terminal_reason text CHECK (terminal_reason IS NULL OR length(terminal_reason) <= 600),
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 completed_at timestamptz,
 CHECK ((session_id IS NULL AND session_generation IS NULL) OR (session_id IS NOT NULL AND session_generation > 0)),
 CHECK (status <> 'blocked' OR blocked_reason IS NOT NULL)
);
-- At most one non-terminal run per enquiry revision (mode changes start a NEW run).
CREATE UNIQUE INDEX workflow_runs_one_active_idx ON workflow_runs (enquiry_id, revision)
 WHERE status IN ('queued','running','pausing','paused','waiting_user','waiting_consent');
CREATE INDEX workflow_runs_enquiry_idx ON workflow_runs (enquiry_id, created_at DESC);
CREATE INDEX workflow_runs_status_idx ON workflow_runs (status, updated_at DESC);
CREATE INDEX workflow_runs_lease_idx ON workflow_runs (lease_expires_at) WHERE status IN ('queued','running','pausing');

CREATE TABLE agent_exchanges (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 run_id uuid NOT NULL REFERENCES workflow_runs(id),
 seq integer NOT NULL CHECK (seq > 0),
 sender text NOT NULL CHECK (sender IN ('intake','nameplate','parts','reply','identification','compatibility_search','fulfilment','verification','controller','workflow','customer','reviewer')),
 recipient text CHECK (recipient IS NULL OR recipient IN ('intake','nameplate','parts','reply','identification','compatibility_search','fulfilment','verification','controller','customer')),
 kind text NOT NULL CHECK (kind IN ('task','request_info','evidence','proposal','challenge','handoff','finding','clarification_request','delegation_request','consent_result','tool_call','tool_result','user_instruction','user_answer','control','limit_reached','action_rejected','late_result_discarded','ready_for_review','step_completed','provider_unavailable')),
 summary text NOT NULL CHECK (length(summary) BETWEEN 1 AND 600),
 payload jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(payload) = 'object' AND octet_length(payload::text) <= 8192),
 evidence_refs text[] NOT NULL DEFAULT '{}' CHECK (cardinality(evidence_refs) <= 12),
 source text NOT NULL CHECK (source IN ('fixture','live','system','user')),
 correlation_id uuid,
 reply_to uuid REFERENCES agent_exchanges(id),
 status text NOT NULL CHECK (status IN ('delivered','handled','rejected','waiting','completed','failed','discarded')),
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (run_id, seq)            -- monotonic, gap-free ordering per run (cursor for reconnects)
);
CREATE INDEX agent_exchanges_run_seq_idx ON agent_exchanges (run_id, seq);

CREATE TABLE run_commands (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 run_id uuid NOT NULL REFERENCES workflow_runs(id),
 actor_id uuid NOT NULL REFERENCES profiles(id),
 type text NOT NULL CHECK (type IN ('pause','resume','cancel','instruct','answer','confirm_nameplate','resolve_delegation','fixture_replay')),
 expected_revision integer CHECK (expected_revision > 0),
 expected_state_version integer CHECK (expected_state_version > 0),
 idempotency_key uuid NOT NULL,
 payload_sha256 text NOT NULL CHECK (payload_sha256 ~ '^[a-f0-9]{64}$'),
 payload jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(payload) = 'object' AND octet_length(payload::text) <= 4096),
 accepted boolean NOT NULL,
 result text NOT NULL CHECK (length(result) <= 300),
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (run_id, idempotency_key)   -- a retried command replays; a reused key with new payload is 409
);
CREATE INDEX run_commands_run_idx ON run_commands (run_id, created_at);

CREATE TABLE pending_actions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 run_id uuid NOT NULL REFERENCES workflow_runs(id),
 enquiry_id uuid NOT NULL REFERENCES enquiries(id),
 revision integer NOT NULL CHECK (revision > 0),
 kind text NOT NULL CHECK (kind IN ('clarification','delegation_consent','nameplate_confirmation')),
 requested_by text NOT NULL,
 code text,
 item_id uuid,
 prompt text NOT NULL CHECK (length(prompt) BETWEEN 1 AND 1000),
 options jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(options) = 'array'),
 allowed_resolutions text[] NOT NULL,
 status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','resolved','cancelled','expired')),
 exchange_id uuid REFERENCES agent_exchanges(id),
 resolved_by uuid REFERENCES profiles(id),
 resolved_at timestamptz,
 resolution text CHECK (resolution IS NULL OR length(resolution) <= 300),
 created_at timestamptz NOT NULL DEFAULT now(),
 CHECK ((status = 'resolved') = (resolved_by IS NOT NULL AND resolved_at IS NOT NULL))
);
-- One open request per run at a time (the run waits on exactly one person).
CREATE UNIQUE INDEX pending_actions_one_open_idx ON pending_actions (run_id) WHERE status = 'open';
CREATE INDEX pending_actions_enquiry_idx ON pending_actions (enquiry_id, status);

-- Exchanges and commands are append-only for application roles.
CREATE OR REPLACE FUNCTION app_private.reject_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'append-only table: % on % is not allowed', TG_OP, TG_TABLE_NAME;
END $$;
CREATE TRIGGER agent_exchanges_append_only BEFORE DELETE OR TRUNCATE ON agent_exchanges
 FOR EACH STATEMENT EXECUTE FUNCTION app_private.reject_mutation();
CREATE TRIGGER run_commands_append_only BEFORE UPDATE OR DELETE OR TRUNCATE ON run_commands
 FOR EACH STATEMENT EXECUTE FUNCTION app_private.reject_mutation();

ALTER TABLE workflow_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_exchanges ENABLE ROW LEVEL SECURITY;
ALTER TABLE run_commands ENABLE ROW LEVEL SECURITY;
ALTER TABLE pending_actions ENABLE ROW LEVEL SECURITY;

-- Visibility follows the enquiry: whoever may read the enquiry (owner / own active demo session /
-- assigned reviewer / admin, enforced by the enquiries policies) may read its runs and exchanges.
CREATE POLICY workflow_runs_read ON workflow_runs FOR SELECT USING (EXISTS (SELECT 1 FROM enquiries e WHERE e.id = workflow_runs.enquiry_id));
CREATE POLICY agent_exchanges_read ON agent_exchanges FOR SELECT USING (EXISTS (SELECT 1 FROM workflow_runs r WHERE r.id = agent_exchanges.run_id));
CREATE POLICY run_commands_read ON run_commands FOR SELECT USING (EXISTS (SELECT 1 FROM workflow_runs r WHERE r.id = run_commands.run_id));
CREATE POLICY pending_actions_read ON pending_actions FOR SELECT USING (EXISTS (SELECT 1 FROM enquiries e WHERE e.id = pending_actions.enquiry_id));
COMMIT;
