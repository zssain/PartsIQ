// F63 Metrics dashboard — typed client for GET /v1/staff/analytics (owner gateway).
//
// Staff-only. Accuracy is always shown with its denominator; a zero denominator is "unavailable"
// (never a fabricated percentage). Demo traffic is excluded unless explicitly included.

import { api } from "@/lib/api";

export interface MetricsView {
  enquiry_count: number;
  approved_count: number;
  clarification_count: number;
  evaluated_count: number;
  correct_count: number;
  median_review_seconds: number | null;
  p95_latency_ms: number | null;
  estimated_cost_usd: string;
}

export interface F63Request {
  start: string;
  end: string;
  include_demo?: boolean;
}

export interface F63Result {
  metrics: MetricsView;
}

// correct / evaluated as a percentage, or null when the denominator is zero.
export function labelledAccuracy(view: MetricsView): number | null {
  if (view.evaluated_count <= 0) return null;
  return view.correct_count / view.evaluated_count;
}

export async function metricsDashboard(request: F63Request): Promise<F63Result> {
  const params = new URLSearchParams({ start: request.start, end: request.end });
  if (request.include_demo) params.set("include_demo", "true");
  return api<F63Result>(`/v1/staff/analytics?${params.toString()}`);
}
