"use client";

import { useState, type JSX } from "react";

import type { ApiError } from "@/lib/api";
import type { F56Request, F56Result } from "@/lib/features/f56_repeat_enquiry";

// F56 Repeat enquiry — one button that re-asks a prior enquiry. It submits only the source id
// (+ a generated idempotency key), creating a fresh enquiry that runs the full pipeline again.
// States: loading / empty / error / success (links to the new conversation).
export function RepeatEnquiry(props: {
  value: F56Result | null;
  loading: boolean;
  error: ApiError | null;
  onAction: (request: F56Request) => Promise<void>;
  sourceEnquiryId?: string;
}): JSX.Element {
  const { value, loading, error, onAction, sourceEnquiryId } = props;
  const [busy, setBusy] = useState(false);

  async function repeat() {
    if (!sourceEnquiryId) return;
    setBusy(true);
    try {
      await onAction({ source_enquiry_id: sourceEnquiryId, idempotency_key: crypto.randomUUID() });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-label="Repeat this enquiry" data-testid="repeat-enquiry">
      <button type="button" onClick={repeat} disabled={busy || loading || !sourceEnquiryId}>
        {busy || loading ? "Creating…" : "Ask again"}
      </button>
      {error ? (
        <p role="alert">
          {error.message}
          {error.requestId ? ` (ref ${error.requestId})` : ""}
        </p>
      ) : null}
      {value === null && !loading && !error ? (
        <p data-testid="repeat-empty">Re-ask this enquiry to check current parts and stock.</p>
      ) : null}
      {value !== null ? (
        <p role="status" data-testid="repeat-created">
          New enquiry created — <a href={`/chat/${value.enquiry.id}`}>open it</a>.
        </p>
      ) : null}
    </section>
  );
}
