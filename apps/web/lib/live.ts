// Live backend client — typed functions over the single FastAPI app at /v1 (fixture mode).
//
// Every mutation carries a fresh Idempotency-Key (crypto.randomUUID) so a retry or double-click
// never duplicates work; the server de-duplicates on that key. Demo identity rides on the
// X-Demo-Token header (set via setDemoToken in lib/api.ts) and only ever scopes a caller to its
// own synthetic session — it never grants a staff role, so staff/ops calls here surface an
// honest permission error offline rather than fabricated data. Reads go straight through api<T>.

import { api, setDemoToken } from "@/lib/api";
import type { EnquiryView, ReplySlots, VerificationResult } from "@/lib/contracts";
import type { DemoSession } from "@/lib/contracts";

// Measured operations metrics from GET /v1/staff/metrics. Every field is nullable: a field the
// backend did not measure reads "not measured" downstream — never a fabricated number. `stages`
// carries per-stage latency so the ops view can show where time was actually spent.
export interface StageLatency {
  stage: string;
  p50_ms: number | null;
  p95_ms: number | null;
}

export interface OpsMetrics {
  stages: StageLatency[];
  tokens_used: number | null;
  retries: number | null;
  // Remaining confirmed allowance (e.g. budgeted calls/tokens the backend will still honour).
  remaining_allowance: number | null;
  updated_at: string | null;
}

// A single persisted pipeline step as recorded in the enquiry timeline. Status reflects ACTUAL
// server state — "waiting" is a real wait on a human/dependency, never a speculative spinner.
export type TimelineStatus = "pending" | "running" | "done" | "waiting" | "failed";

export interface TimelineEvent {
  step: string;
  label: string;
  at: string;
  status: TimelineStatus;
  // Optional concise evidence line (step input/output / tool-result summary). Never a hidden
  // model chain-of-thought — only observable step outcomes.
  detail?: string | null;
  // Optional retry counter when a step was re-attempted.
  attempt?: number | null;
}

export interface TimelineView {
  enquiry_id: string;
  events: TimelineEvent[];
}

// Customer-facing progress snapshot. `step` is the current pipeline step; `wait_reason` explains
// a real wait (e.g. "awaiting human review"); `revision` guards against stale optimistic state.
export interface ProgressView {
  step: string;
  wait_reason: string | null;
  revision: number;
  updated_at: string;
}

export interface CreateEnquiryRequest {
  text: string;
  locale?: "en" | "ar";
  destination_warehouse_id?: number;
}

export interface CreateEnquiryResult {
  id: string;
}

export interface HistoryResult {
  enquiries: EnquiryView[];
  next_cursor: string | null;
}

export interface DemoScenario {
  id: string;
  title: string;
  blurb: string;
}

export interface ScenariosResult {
  scenarios: DemoScenario[];
}

function idempotencyKey(): Record<string, string> {
  return { "idempotency-key": crypto.randomUUID() };
}

// Customer — create a new enquiry. 202 Accepted with the new enquiry id.
export async function createEnquiry(request: CreateEnquiryRequest): Promise<CreateEnquiryResult> {
  // EnquiryCreate requires text + locale + destination_warehouse_id; default the demo warehouse.
  const body = {
    text: request.text,
    locale: request.locale ?? "en",
    destination_warehouse_id: request.destination_warehouse_id ?? 1,
  };
  return api<CreateEnquiryResult>("/v1/enquiries", {
    method: "POST",
    headers: idempotencyKey(),
    body: JSON.stringify(body),
  });
}

// Customer — fetch the current enquiry snapshot.
export async function getEnquiry(id: string, signal?: AbortSignal): Promise<EnquiryView> {
  return api<EnquiryView>(`/v1/enquiries/${id}`, { signal });
}

// Customer — fetch the lightweight progress view (current step + wait reason).
export async function getProgress(id: string, signal?: AbortSignal): Promise<ProgressView> {
  return api<ProgressView>(`/v1/enquiries/${id}/progress`, { signal });
}

// Customer — fetch the PERSISTED timeline events that drive the animated step list.
export async function getTimeline(id: string, signal?: AbortSignal): Promise<TimelineView> {
  return api<TimelineView>(`/v1/enquiries/${id}/timeline`, { signal });
}

// Human decision — approve the reviewed draft. Mutation → idempotency key.
export async function approveEnquiry(id: string): Promise<EnquiryView> {
  return api<EnquiryView>(`/v1/enquiries/${id}/approve`, {
    method: "POST",
    headers: idempotencyKey(),
    body: JSON.stringify({ enquiry_id: id }),
  });
}

// Customer — the caller's own enquiry history (ownership enforced server-side).
export async function listHistory(cursor?: string | null): Promise<HistoryResult> {
  const query = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
  return api<HistoryResult>(`/v1/enquiries${query}`);
}

// Demo — the available synthetic scenarios.
export async function listScenarios(): Promise<ScenariosResult> {
  return api<ScenariosResult>("/v1/demo/scenarios");
}

// Demo — start a server-side synthetic session.
export async function createDemoSession(): Promise<DemoSession> {
  return api<DemoSession>("/v1/demo/sessions", {
    method: "POST",
    headers: idempotencyKey(),
  });
}

// Staff/ops — measured operational metrics. A demo caller is role-denied offline (403/404/503);
// callers surface an honest empty state rather than fabricate numbers.
export async function getMetrics(signal?: AbortSignal): Promise<OpsMetrics> {
  return api<OpsMetrics>("/v1/staff/metrics", { signal });
}

// ────────────────────────────────────────────────────────────────────────────────────────────
// Reviewer side (F03 presentational role switch). In fixture mode the canonical /v1/staff review
// surface is served under the caller's OWN demo session scope — so a reviewer only ever sees this
// session's enquiries. A foreign id is a 404 ("not available"), never fabricated. These functions
// mirror the review ReviewView / ApprovalResult / ReviewResult wire shapes from the backend spec.
// ────────────────────────────────────────────────────────────────────────────────────────────

// One warehouse allocation line for a fact item — the VERIFIED fulfilment split (database truth,
// not a model opinion). `transfer_days` is an estimate the UI must label as not guaranteed.
export interface FactAllocation {
  warehouse_id: number | string;
  quantity: number;
  transfer_days: number;
}

// A single verified fact item: the part the database confirms, with its source reference and the
// allocation plan. This is the "Database evidence" region's content — never the model's suggestion.
export interface FactItem {
  part_number: string;
  name_en: string;
  name_ar: string;
  requested_quantity: number;
  allocations: FactAllocation[];
  source_reference: string;
}

export interface Facts {
  items: FactItem[];
}

// The review workspace resource (GET /v1/staff/enquiries/{id}). `draft` holds the model's proposed
// reply slots (a SUGGESTION); `facts` holds the verified database evidence; `verification` records
// the deterministic gate. `enquiry.revision` is the optimistic-concurrency token for a decision.
export interface ReviewView {
  enquiry: EnquiryView;
  facts: Facts | null;
  draft: ReplySlots | null;
  verification: VerificationResult | null;
  assigned_to: string | null;
}

// Result of POST /v1/staff/enquiries/{id}/approve. `already_applied` is true when an idempotent
// retry hit an already-committed decision (so a double-click publishes exactly once).
export interface ApprovalResult {
  decision_id: string;
  message_id: string;
  revision: number;
  already_applied: boolean;
}

// Result of POST /v1/staff/enquiries/{id}/reject. `status` is the authoritative post-decision state.
export interface ReviewResult {
  decision_id: string;
  revision: number;
  status: EnquiryView["status"];
}

export interface InboxResult {
  items: EnquiryView[];
  next_cursor: string | null;
}

// Demo identity bootstrap (F04 isolation). Reads the one anonymous session token from
// sessionStorage, generating + persisting it once with crypto.randomUUID, then registers it via
// setDemoToken so every subsequent api<T> call carries X-Demo-Token. Returns the token. Safe to
// call repeatedly; on the server (no window) it is a no-op that returns an empty string.
const DEMO_TOKEN_KEY = "pq-demo-token";
export function ensureDemoToken(): string {
  if (typeof window === "undefined") return "";
  let token = window.sessionStorage.getItem(DEMO_TOKEN_KEY);
  if (!token) {
    token = crypto.randomUUID();
    window.sessionStorage.setItem(DEMO_TOKEN_KEY, token);
  }
  setDemoToken(token);
  return token;
}

// Reviewer — the caller's own-session review queue (optionally filtered by status). Ownership is
// enforced server-side; a demo session only ever sees its own enquiries.
export async function listInbox(status?: string, signal?: AbortSignal): Promise<InboxResult> {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return api<InboxResult>(`/v1/staff/enquiries${query}`, { signal });
}

// Reviewer — the full review workspace for one enquiry (draft + verified facts + verification).
// A foreign id resolves to a 404 which callers render as "not available".
export async function getWorkspace(id: string, signal?: AbortSignal): Promise<ReviewView> {
  return api<ReviewView>(`/v1/staff/enquiries/${id}`, { signal });
}

// Human decision — approve the current reviewed draft. Carries the expected revision (optimistic
// concurrency: a 409 means the data changed under the reviewer) and a fresh draft_id; the mutation
// is idempotency-keyed so a retry/double-click publishes exactly once.
export async function approveReview(id: string, revision: number): Promise<ApprovalResult> {
  return api<ApprovalResult>(`/v1/staff/enquiries/${id}/approve`, {
    method: "POST",
    headers: idempotencyKey(),
    body: JSON.stringify({ enquiry_id: id, expected_revision: revision, draft_id: crypto.randomUUID() }),
  });
}

// Human decision — reject with a required reason. Same optimistic-concurrency revision guard.
export async function rejectReview(id: string, revision: number, reason: string): Promise<ReviewResult> {
  return api<ReviewResult>(`/v1/staff/enquiries/${id}/reject`, {
    method: "POST",
    headers: idempotencyKey(),
    body: JSON.stringify({ enquiry_id: id, expected_revision: revision, reason }),
  });
}
