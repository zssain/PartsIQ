"use client";

import { useState, type JSX } from "react";

import type { ApiError } from "@/lib/api";
import type { F43Request, F43Result } from "@/lib/features/f43_overdue_indicators";

// F43 Overdue badge — shows the review deadline (local display of a UTC instant) and an overdue
// marker for unresolved enquiries. The deadline is a triage aid, not an SLA. States: loading /
// empty / error / success.
export function OverdueBadge(props: {
  value: F43Result | null;
  loading: boolean;
  error: ApiError | null;
  onAction: (request: F43Request) => Promise<void>;
  enquiryId?: string;
}): JSX.Element {
  const { value, loading, error, onAction, enquiryId } = props;
  const [busy, setBusy] = useState(false);

  async function refresh() {
    if (!enquiryId) return;
    setBusy(true);
    try {
      await onAction({ enquiry_id: enquiryId });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-label="Review deadline" data-testid="overdue-badge">
      <button type="button" onClick={refresh} disabled={busy || loading || !enquiryId}>
        {busy || loading ? "Checking…" : "Check deadline"}
      </button>
      {error ? (
        <p role="alert">
          {error.message}
          {error.requestId ? ` (ref ${error.requestId})` : ""}
        </p>
      ) : null}
      {value === null && !loading && !error ? (
        <p data-testid="deadline-empty">Deadline not loaded.</p>
      ) : null}
      {value !== null ? (
        value.overdue ? (
          <p role="status" data-testid="overdue">
            Overdue (due {new Date(value.due_at).toLocaleString()}). Triage aid, not an SLA.
          </p>
        ) : (
          <p role="status" data-testid="on-time">
            Due {new Date(value.due_at).toLocaleString()}.
          </p>
        )
      ) : null}
    </section>
  );
}
