"use client";

import { type JSX } from "react";

import type { ApiError } from "@/lib/api";
import { isStale, type F44Request, type F44Result } from "@/lib/features/f44_conversation_summary";

// F44 Conversation summary — staff-only. Requests a fresh summary and displays the current one,
// marking it stale if the enquiry has moved past the revision it summarized. React escapes the
// text. If the summary is unavailable (budget exhausted), the reviewer still has the full
// conversation. States: loading / empty / error / success.
export function ConversationSummary(props: {
  value: F44Result | null;
  loading: boolean;
  error: ApiError | null;
  onAction: (request: F44Request) => Promise<void>;
  enquiryId?: string;
  currentRevision?: number;
}): JSX.Element {
  const { value, loading, error, onAction, enquiryId, currentRevision } = props;

  async function regenerate() {
    if (!enquiryId) return;
    await onAction({ enquiry_id: enquiryId, expected_revision: currentRevision ?? 1 });
  }

  return (
    <section aria-label="Conversation summary (staff only)" data-testid="conversation-summary">
      <button type="button" onClick={regenerate} disabled={loading || !enquiryId}>
        {loading ? "Summarizing…" : "Summarize conversation"}
      </button>
      {error ? (
        <p role="alert">
          Summary unavailable — the full conversation is still shown. {error.message}
        </p>
      ) : null}
      {value === null && !loading && !error ? (
        <p data-testid="summary-empty">No summary yet. The full conversation is always available below.</p>
      ) : null}
      {value !== null ? (
        <div data-testid="summary">
          {currentRevision !== undefined && isStale(value.revision, currentRevision) ? (
            <p role="note" data-testid="summary-stale">Summary is stale (revision {value.revision}).</p>
          ) : null}
          <p>{value.summary}</p>
        </div>
      ) : null}
    </section>
  );
}
