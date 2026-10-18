// Live backend client — typed functions over the single FastAPI app at /v1 (fixture mode).
//
// Every mutation carries a fresh Idempotency-Key (crypto.randomUUID) so a retry or double-click
// never duplicates work; the server de-duplicates on that key. Demo identity rides on the
// X-Demo-Token header (set via setDemoToken in lib/api.ts) and only ever scopes a caller to its
// own synthetic session — it never grants a staff role, so staff/ops calls here surface an
// honest permission error offline rather than fabricated data. Reads go straight through api<T>.

import { api } from "@/lib/api";
import type { EnquiryView } from "@/lib/contracts";
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
  return api<CreateEnquiryResult>("/v1/enquiries", {
    method: "POST",
    headers: idempotencyKey(),
    body: JSON.stringify(request),
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
