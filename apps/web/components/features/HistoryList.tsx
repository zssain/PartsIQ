"use client";

import { useState, type JSX } from "react";

import type { ApiError } from "@/lib/api";
import type { F19Request, F19Result } from "@/lib/features/f19_enquiry_history";

// F19 Enquiry history — owned enquiries newest-first with status, each linking to the full
// conversation. "Load more" pages via the opaque next_cursor; it submits only typed
// identifiers. A foreign/expired link resolves to a scoped 404 on the conversation page.
export function HistoryList(props: {
  value: F19Result | null;
  loading: boolean;
  error: ApiError | null;
  onAction: (request: F19Request) => Promise<void>;
}): JSX.Element {
  const { value, loading, error, onAction } = props;
  const [busy, setBusy] = useState(false);

  async function loadMore() {
    if (!value?.next_cursor) return;
    setBusy(true);
    try {
      await onAction({ cursor: value.next_cursor });
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <p data-testid="history-loading">Loading your enquiries…</p>;
  if (error)
    return (
      <p role="alert">
        {error.message}
        {error.requestId ? ` (ref ${error.requestId})` : ""}
      </p>
    );
  if (value === null) return <p data-testid="history-empty">No enquiries loaded yet.</p>;
  if (value.enquiries.length === 0)
    return <p data-testid="history-empty">You have no enquiries yet.</p>;

  return (
    <section aria-label="Your enquiries" data-testid="history-list">
      <ul>
        {value.enquiries.map((enquiry) => (
          <li key={enquiry.id} data-status={enquiry.status}>
            <a href={`/chat/${enquiry.id}`}>Enquiry {enquiry.id.slice(0, 8)}</a>
            <span data-testid="history-status"> — {enquiry.status}</span>
            <time dateTime={enquiry.updated_at}> {new Date(enquiry.updated_at).toLocaleString()}</time>
          </li>
        ))}
      </ul>
      {value.next_cursor ? (
        <button type="button" onClick={loadMore} disabled={busy}>
          {busy ? "Loading…" : "Load more"}
        </button>
      ) : null}
    </section>
  );
}
