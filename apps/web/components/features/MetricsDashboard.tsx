"use client";

import { type JSX } from "react";

import type { ApiError } from "@/lib/api";
import { labelledAccuracy, type F63Request, type F63Result } from "@/lib/features/f63_metrics_dashboard";

// F63 Metrics dashboard — shows volume/status/review-time/clarification + labelled accuracy WITH
// its denominator. A zero denominator reads "unavailable" (never a fabricated percentage). Demo
// traffic is separated server-side. States: loading / empty / error / success.
export function MetricsDashboard(props: {
  value: F63Result | null;
  loading: boolean;
  error: ApiError | null;
  onAction: (request: F63Request) => Promise<void>;
}): JSX.Element {
  const { value, loading, error } = props;

  if (loading) return <p data-testid="metrics-loading">Loading metrics…</p>;
  if (error)
    return (
      <p role="alert">
        {error.message}
        {error.requestId ? ` (ref ${error.requestId})` : ""}
      </p>
    );
  if (value === null) return <p data-testid="metrics-empty">No metrics loaded.</p>;

  const m = value.metrics;
  const accuracy = labelledAccuracy(m);
  return (
    <section aria-label="Metrics" data-testid="metrics-dashboard">
      <dl>
        <dt>Enquiries</dt>
        <dd data-testid="m-volume">{m.enquiry_count}</dd>
        <dt>Approved</dt>
        <dd>{m.approved_count}</dd>
        <dt>Clarifications</dt>
        <dd>{m.clarification_count}</dd>
        <dt>Median review time</dt>
        <dd>{m.median_review_seconds === null ? "unavailable" : `${m.median_review_seconds}s`}</dd>
        <dt>Labelled accuracy</dt>
        <dd data-testid="m-accuracy">
          {accuracy === null
            ? "unavailable"
            : `${Math.round(accuracy * 100)}% (${m.correct_count}/${m.evaluated_count})`}
        </dd>
        <dt>Estimated AI cost</dt>
        <dd>${m.estimated_cost_usd}</dd>
      </dl>
    </section>
  );
}
