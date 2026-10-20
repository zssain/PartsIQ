// Typed client for the workspace contracts (docs/API_WORKSPACE.md). One owned contract source:
// these interfaces mirror the FastAPI responses in apps/api/partsiq/workspace/*.py. Every
// mutation takes an Idempotency-Key supplied by the caller (see useIdempotentAction) so a retry
// of the SAME logical operation reuses its key and can never act twice.

import { api } from "@/lib/api";

export type Capability =
  | "enquiry.create" | "enquiry.read_own" | "machines.manage_own" | "run.control_own"
  | "review.queue" | "review.decide" | "review.all" | "run.control_assigned" | "run.control_all"
  | "catalogue.browse" | "catalogue.import" | "catalogue.publish"
  | "admin.users" | "admin.assign" | "analytics.read" | "audit.read" | "jobs.read" | "jobs.retry"
  | "evaluation.run" | "ai.allowance";

export interface Identity {
  id: string;
  roles: string[];
  is_anonymous: boolean;
  kind: "demo" | "account";
  display_name: string | null;
  email: string | null;
  capabilities: Capability[];
  demo_session_id: string | null;
  demo_session_generation: number | null;
  demo_expires_at: string | null;
  data_source: string | null;
  ai_mode: string | null;
  live_available: boolean;
  collaboration_enabled: boolean;
}

export type EnquiryStatus = "received" | "processing" | "needs_information" | "awaiting_review" | "approved" | "rejected" | "failed";
export type RunMode = "guided" | "collaboration";
export type RunStatus =
  | "queued" | "running" | "pausing" | "paused" | "waiting_user" | "waiting_consent" | "blocked"
  | "awaiting_review" | "completed" | "cancelled" | "failed" | "superseded" | "needs_staff";

export interface EnquirySummary {
  id: string; revision: number; status: EnquiryStatus; step: string; title: string;
  created_at: string; updated_at: string; mode: RunMode; priority: "normal" | "urgent";
  due_at: string | null; overdue: boolean; run_status: RunStatus | null;
  execution_source: "fixture" | "live" | null; assigned_to: string | null; assigned_label: string | null;
  items: number; pending_question: string | null;
}

export interface Page<T> { items: T[]; total: number; next_cursor: number | null }

export interface Dashboard {
  scope: "demo" | "account";
  counts: Partial<Record<EnquiryStatus, number>>;
  total: number;
  needs_you: { id: string; question: string; updated_at: string }[];
  recent: EnquirySummary[];
  review: null | { awaiting_review: number; needs_information: number; exceptions: number; overdue: number; assigned_to_me: number; unassigned: number };
  active_runs: number;
}

export interface Candidate { part_id: number; part_number: string; name_en: string; name_ar: string; score: number; reasons: string[]; source_reference: string; superseded_from: string[] }

export interface ItemDetail {
  id: string; ordinal: number; description: string; quantity: string | null; quantity_assumed: boolean;
  model_text: string | null; serial_text: string | null; status: string; configuration_label: string | null;
  identification_note: string | null; clarification_code: string | null; clarification_text: string | null;
  quoted_number_note: string | null;
  selected: null | (Candidate & { matched_terms: string[]; selection_source: string | null });
  candidates: Candidate[];
  plan: null | { strategy: string; message: string; shortage: number; lines: { warehouse_code: string; warehouse_name: string; quantity: number; transfer_days: number; observed_at: string }[] };
}

export interface PendingAction {
  id: string; run_id: string; enquiry_id: string; revision: number;
  kind: "clarification" | "delegation_consent" | "nameplate_confirmation";
  code: string | null; requested_by: string; requested_by_label: string; prompt: string;
  options: { value: string; label: string; part_number?: string }[]; allowed_resolutions: string[];
  status: string; item_id: string | null; created_at: string;
}

export interface RosterEntry { id: string; label: string; type: "agent" | "service" | "workflow"; state: "idle" | "working" | "waiting" | "active" | "done"; messages: number }

export interface Run {
  id: string; enquiry_id: string; revision: number; current_revision: number; stale: boolean;
  mode: RunMode; status: RunStatus; control: string; execution_source: "fixture" | "live";
  created_by: string; catalogue_version_id: string; limits: Record<string, number | string>;
  usage: { agent_turns: number; tool_calls: number; output_tokens: number | null; input_tokens: number | null; estimated_usd: string | null; retries: number; active_seconds: number };
  state_version: number; in_flight: boolean; current_step: string | null; blocked_reason: string | null;
  terminal_reason: string | null; created_at: string; updated_at: string; completed_at: string | null;
  pending: PendingAction[]; roster: RosterEntry[]; carried_from: string | null; available_actions: string[];
}

export interface Exchange {
  id: string; seq: number; run_id: string; sender: string; sender_label: string;
  recipient: string | null; recipient_label: string | null; kind: string; kind_label: string;
  summary: string; payload: Record<string, unknown>; evidence_refs: string[];
  source: "fixture" | "live" | "system" | "user"; correlation_id: string | null; reply_to: string | null;
  status: string; created_at: string;
}

export interface EnquiryDetail {
  id: string; revision: number; status: EnquiryStatus; step: string; wait_reason: string | null;
  locale: "en" | "ar"; language: string; urgency: string; priority: string;
  destination: { id: number; name: string }; created_at: string; updated_at: string; due_at: string | null;
  mode: RunMode; catalogue_version_id: string | null; catalogue_current: boolean;
  messages: { id: string; revision: number; kind: string; body: string; created_at: string }[];
  items: ItemDetail[];
  attachments: { id: string; status: string; media_type: string; width: number | null; height: number | null; error_code: string | null }[];
  nameplate: null | { model_text: string | null; serial_text: string | null; issues: string[]; confirmed: boolean; confirmed_model: string | null; confirmed_serial: string | null; source: string };
  pending_question: string | null; pending_code: string | null; pending: PendingAction[];
  run: Run | null;
  runs: { id: string; mode: RunMode; status: RunStatus; revision: number; created_at: string; execution_source: string }[];
  events: { step: string; label: string; at: string; status: string; detail: string | null; revision: number }[];
  draft: null | { id: string; rendered: string; source: string; published: boolean };
  verification: null | { passed: boolean; failures: { code: string; detail: string | null }[] };
  decision: null | { kind: "approved" | "rejected"; at: string; reason: string | null; revision: number };
  published_reply: null | { id: string; body: string; revision: number; created_at: string };
  assigned_to: string | null; instructions: string[]; can_review: boolean; can_control: boolean; is_owner: boolean;
}

export interface ReviewDetail extends EnquiryDetail {
  notes: { id: string; author_id: string; author_label: string | null; body: string; created_at: string }[];
  reviewers: { id: string; label: string; roles: string[] }[];
  assigned_label: string | null; revisions: number[];
  decisions: { id: string; kind: string; revision: number; at: string; reason: string | null; actor_label: string | null }[];
  evidence: null | { active_catalogue_version_id: string; stock: { part_id: number; warehouse_id: number; warehouse_name: string; available: string; updated_at: string }[] };
  review_ready_at: string | null; can_assign: boolean; can_decide: boolean;
}

export interface Warehouse { id: number; code: string; name: string; region: string }

const k = (key: string) => ({ "idempotency-key": key });

export const ws = {
  me: (signal?: AbortSignal) => api<Identity>("/v1/me", { signal }),
  status: () => api<Record<string, unknown> & { dependencies: { name: string; state: string; detail: string }[]; limits: Record<string, unknown> }>("/v1/workspace/status"),
  dashboard: (signal?: AbortSignal) => api<Dashboard>("/v1/workspace/dashboard", { signal }),
  enquiries: (params: Record<string, string | number | undefined>, signal?: AbortSignal) => {
    const q = new URLSearchParams();
    for (const [name, value] of Object.entries(params)) if (value !== undefined && value !== "") q.set(name, String(value));
    return api<Page<EnquirySummary>>(`/v1/workspace/enquiries?${q}`, { signal });
  },
  warehouses: () => api<Warehouse[]>("/v1/warehouses"),
  create: (body: { text: string; locale: "en" | "ar"; destination_warehouse_id: number }, mode: RunMode, key: string, defer = false) =>
    api<{ id: string; revision: number; status: EnquiryStatus }>(`/v1/enquiries?mode=${mode}${defer ? "&defer=true" : ""}`, { method: "POST", headers: k(key), body: JSON.stringify(body) }),
  detail: (id: string, signal?: AbortSignal) => api<EnquiryDetail>(`/v1/enquiries/${id}/detail`, { signal }),
  message: (id: string, text: string, expected_revision: number, key: string) =>
    api(`/v1/enquiries/${id}/messages`, { method: "POST", headers: k(key), body: JSON.stringify({ text, expected_revision }) }),
  attachSample: (id: string, key: string) => api<{ id: string }>(`/v1/enquiries/${id}/attachments/sample`, { method: "POST", headers: k(key) }),
  upload: (id: string, file: File, key: string) => api<{ id: string }>(`/v1/enquiries/${id}/attachments`, { method: "POST", headers: { ...k(key), "content-type": file.type }, body: file }),
  runs: (id: string) => api<Run[]>(`/v1/enquiries/${id}/runs`),
  run: (runId: string, signal?: AbortSignal) => api<Run>(`/v1/runs/${runId}`, { signal }),
  events: (runId: string, after: number, signal?: AbortSignal) => api<{ items: Exchange[]; next_after: number; run: Run }>(`/v1/runs/${runId}/events?after=${after}&limit=200`, { signal }),
  startRun: (id: string, mode: RunMode, expected_revision: number, key: string) =>
    api<Run>(`/v1/enquiries/${id}/runs`, { method: "POST", headers: k(key), body: JSON.stringify({ mode, expected_revision }) }),
  command: (runId: string, body: { type: string; expected_revision: number; expected_state_version?: number; payload?: Record<string, unknown> }, key: string) =>
    api<{ id: string; result: string; replayed: boolean; run: Run }>(`/v1/runs/${runId}/commands`, { method: "POST", headers: k(key), body: JSON.stringify({ payload: {}, ...body }) }),
  // Review
  reviewDetail: (id: string, signal?: AbortSignal) => api<ReviewDetail>(`/v1/staff/enquiries/${id}/detail`, { signal }),
  approve: (id: string, body: { expected_revision: number; draft_id: string; edited_slots?: unknown }, key: string) =>
    api<{ decision_id: string; message_id: string; revision: number; already_applied: boolean }>(`/v1/staff/enquiries/${id}/approve`, { method: "POST", headers: k(key), body: JSON.stringify({ enquiry_id: id, ...body }) }),
  reject: (id: string, body: { expected_revision: number; reason: string }, key: string) =>
    api<{ decision_id: string; status: string }>(`/v1/staff/enquiries/${id}/reject`, { method: "POST", headers: k(key), body: JSON.stringify({ enquiry_id: id, ...body }) }),
  note: (id: string, body: string, key: string) => api(`/v1/staff/enquiries/${id}/notes`, { method: "POST", headers: k(key), body: JSON.stringify({ body }) }),
  assign: (id: string, assignee_id: string | null, expected_revision: number, key: string) =>
    api(`/v1/staff/enquiries/${id}/assignment`, { method: "PUT", headers: k(key), body: JSON.stringify({ assignee_id, expected_revision }) }),
  // Catalogue
  catalogue: (params: Record<string, string | number | undefined>, signal?: AbortSignal) => {
    const q = new URLSearchParams();
    for (const [name, value] of Object.entries(params)) if (value !== undefined && value !== "") q.set(name, String(value));
    return api<Page<CataloguePart> & { categories: string[]; models: string[]; version: CatalogueVersion | null }>(`/v1/catalogue/search?${q}`, { signal });
  },
  part: (number: string) => api<PartDetail>(`/v1/catalogue/parts/${encodeURIComponent(number)}/detail`),
  versions: () => api<{ items: { id: string; label: string; state: string; content_sha256: string; published_at: string | null; source: string }[] }>("/v1/admin/catalogue/versions"),
  // Imports
  imports: () => api<ImportSummary[]>("/v1/admin/imports"),
  stageImport: (filename: string, size: number, key: string) => api<{ id: string }>("/v1/admin/imports", { method: "POST", headers: k(key), body: JSON.stringify({ filename, format: "csv", size_bytes: Math.max(1, size) }) }),
  uploadImport: (id: string, text: string) => api(`/v1/admin/imports/${id}/content`, { method: "PUT", headers: { "content-type": "text/csv" }, body: text }),
  validateImport: (id: string) => api(`/v1/admin/imports/${id}/validate`, { method: "POST" }),
  importPreview: (id: string) => api<ImportPreview>(`/v1/admin/imports/${id}/preview`),
  publishImport: (id: string, content_sha256: string, expected_active_version_id: string, key: string) =>
    api(`/v1/admin/imports/${id}/publish`, { method: "POST", headers: k(key), body: JSON.stringify({ content_sha256, expected_active_version_id }) }),
  // Admin
  members: () => api<{ source: "sandbox" | "supabase" | "unavailable"; items: Member[]; note: string | null }>("/v1/admin/members"),
  invite: (body: { email: string; display_name?: string; roles: string[] }, key: string) => api<Member>("/v1/admin/members/invite", { method: "POST", headers: k(key), body: JSON.stringify(body) }),
  setRoles: (id: string, roles: string[], expected_version: number, key: string) => api<Member>(`/v1/admin/members/${id}/roles`, { method: "PUT", headers: k(key), body: JSON.stringify({ roles, expected_version }) }),
  audit: (params: Record<string, string | number | undefined>) => {
    const q = new URLSearchParams();
    for (const [name, value] of Object.entries(params)) if (value !== undefined && value !== "") q.set(name, String(value));
    return api<Page<AuditRow>>(`/v1/admin/audit?${q}`);
  },
  jobs: (status?: string) => api<Page<JobRow> & { counts: Record<string, number>; dependencies: { name: string; state: string; detail: string }[] }>(`/v1/admin/jobs${status ? `?status=${status}` : ""}`),
  retryJob: (id: string, expected_revision: number, key: string) => api(`/v1/jobs/${id}/retry`, { method: "POST", headers: k(key), body: JSON.stringify({ expected_revision }) }),
  analytics: () => api<Analytics>("/v1/admin/analytics"),
  evaluations: () => api<EvaluationRow[]>("/v1/admin/evaluations"),
  runEvaluation: (key: string) => api<{ id: string }>("/v1/admin/evaluations", { method: "POST", headers: k(key), body: JSON.stringify({ suite: "deterministic", include_demo: true }) }),
  evaluation: (id: string) => api<{ run_id: string; state: string; total: number; passed: number; failed: number; results: { case_id: string; passed: boolean; actual: { status: string; part_ids: number[]; clarification_code: string | null } }[] }>(`/v1/admin/evaluations/${id}`),
  corrections: () => api<{ id: string; enquiry_id: string; revision: number; field: string; before: string | null; after: string | null; reviewed: boolean; created_at: string }[]>("/v1/admin/corrections"),
  reviewCorrection: (id: string, key: string) => api(`/v1/admin/corrections/${id}/reviewed`, { method: "POST", headers: k(key) }),
  // Machines
  machines: () => api<{ items: { id: string; label: string; model_text: string; serial_text: string; created_at: string }[] }>("/v1/machines"),
  saveMachine: (body: { label: string; model_text: string; serial_text: string }, key: string) => api("/v1/machines", { method: "POST", headers: k(key), body: JSON.stringify(body) }),
  archiveMachine: (id: string) => api(`/v1/machines/${id}`, { method: "DELETE" }),
  checkMachine: (id: string) => api<{ state: string; configuration_label: string | null; note: string }>(`/v1/machines/${id}/check`),
  resetDemo: (sessionId: string, key: string) => api<{ id: string; generation: number; expires_at: string }>(`/v1/demo/sessions/${sessionId}/reset`, { method: "POST", headers: k(key), body: JSON.stringify({ expected_revision: 1 }) }),
};

export interface CataloguePart { id: number; part_number: string; name_en: string; name_ar: string; category: string; unit_of_measure: string; is_active: boolean; aliases: string[] }
export interface CatalogueVersion { id: string; label: string; published_at: string | null; source: string; content_sha256: string }
export interface PartDetail {
  id: number; part_number: string; name_en: string; name_ar: string; description_en: string; category: string; unit_of_measure: string; is_active: boolean;
  aliases: { alias: string; language: string }[];
  compatibility: { brand: string; model_code: string; config_code: string; quantity_per_unit: number; source_reference: string }[];
  supersedes: { old: string; effective_date: string; reason: string }[]; superseded_by: { new: string; effective_date: string; reason: string }[];
  stock: { warehouse_code: string; warehouse_name: string; available: number; observed_at: string }[];
  catalogue_version_id: string; synthetic: boolean;
}
export interface ImportSummary { id: string; filename: string; state: string; rows: number; issues: number; created_at: string; version_id: string | null }
export interface ImportPreview {
  id: string; state: string; row_count: number; issues: { row_number: number; field: string; code: string; message: string }[];
  version_id: string | null; content_sha256: string | null; filename: string; created_at: string;
  preview: { added?: Record<string, number>; changed?: Record<string, number>; samples?: { row_number: number; entity_type: string; action: string; summary: string }[] };
  base_version_id: string | null; active_version_id: string; base_is_active: boolean;
}
export interface Member { id: string; email: string | null; display_name: string; roles: string[]; kind: string; created_at: string; last_sign_in_at: string | null; version: number; is_you: boolean }
export interface AuditRow { seq: number; actor_type: string; actor_id: string; actor_label: string; action: string; entity_type: string; entity_id: string; enquiry_id: string | null; revision: number | null; payload: Record<string, unknown>; request_id: string; created_at: string }
export interface JobRow { id: string; status: string; kind: string; attempts: number; error_code: string | null; resource_id: string | null; created_at: string; updated_at: string; error_category: string | null; retryable: boolean; execution_source: string; revision: number | null }
export interface EvaluationRow { id: string; suite: string; state: string; total: number; passed: number; failed: number; dataset: string; dataset_sha256: string; created_at: string }
export interface Analytics {
  scope: "demo" | "account"; scope_note: string;
  enquiries: { total: number; by_status: Record<string, number> };
  runs: { total: number; by_mode: Record<string, Record<string, number>>; failed: number; retries: number; cancelled: number };
  exchanges: number;
  review_seconds: { median: number | null; p95: number | null; samples: number };
  latency_ms: Record<string, { p50_ms: number | null; p95_ms: number | null; samples: number }>;
  tokens: null | { input: number; output: number; estimated_usd: string }; tokens_note: string | null;
  allowance: null | { confirmed_usd: string; consumed_usd: string; reserved_usd: string; remaining_usd: string }; allowance_note: string | null;
  accuracy: null | { passed: number; total: number; dataset: string; run_id: string; at: string }; accuracy_note: string | null;
  demo_workspaces_active: number | null;
}

export const TERMINAL_RUN: RunStatus[] = ["awaiting_review", "completed", "cancelled", "failed", "superseded", "needs_staff"];
