"use client";

import { useCallback, useEffect, useState, type JSX } from "react";

import { ApiError } from "@/lib/api";
import { listInbox } from "@/lib/live";
import type { EnquiryView } from "@/lib/contracts";

// Reviewer inbox (F03/F04). Lists THIS session's own review queue (listInbox('awaiting_review')).
// Ownership/scope is enforced server-side, so the reviewer never sees another session's enquiry.
// Honest states: loading / empty / error+retry (request id) / permission (401/403 → signed-in).

const PERMISSION = new Set([401, 403]);

function firstLine(enquiry: EnquiryView): string {
  const customer = enquiry.messages.find((m) => m.kind === "customer");
  const body = (customer ?? enquiry.messages[0])?.body ?? "";
  return body.length > 120 ? `${body.slice(0, 120)}…` : body || "(no message yet)";
}

export function ReviewerInbox({ onOpen }: { onOpen: (id: string) => void }): JSX.Element {
  const [items, setItems] = useState<EnquiryView[] | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const result = await listInbox("awaiting_review");
      setItems(result.items);
    } catch (err) {
      if (err instanceof ApiError) setError(err);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (error && PERMISSION.has(error.status)) {
    return (
      <section aria-label="Review inbox" data-testid="reviewer-inbox" className="pq-card">
        <p data-testid="inbox-permission">
          Reviewing requires a signed-in staff session.{error.requestId ? ` (ref ${error.requestId})` : ""}
        </p>
      </section>
    );
  }

  if (error && items === null) {
    return (
      <section aria-label="Review inbox" data-testid="reviewer-inbox" className="pq-card">
        <p role="alert">
          Could not load the review inbox. {error.message}
          {error.requestId ? ` (ref ${error.requestId})` : ""}
        </p>
        <button type="button" className="pq-btn pq-btn-ghost" onClick={() => void load()} data-testid="inbox-retry">
          Retry
        </button>
      </section>
    );
  }

  if (items === null) {
    return (
      <section aria-label="Review inbox" data-testid="reviewer-inbox" className="pq-card">
        <p data-testid="inbox-loading">Loading your review queue…</p>
      </section>
    );
  }

  if (items.length === 0) {
    return (
      <section aria-label="Review inbox" data-testid="reviewer-inbox" className="pq-card">
        <p data-testid="inbox-empty" className="pq-muted">
          Nothing is awaiting your review yet. Submit an enquiry as the customer, then switch back here.
        </p>
      </section>
    );
  }

  return (
    <section aria-label="Review inbox" data-testid="reviewer-inbox" className="pq-card">
      <h2 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: 10 }}>Awaiting your review</h2>
      <ul data-testid="inbox-items" style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 10 }}>
        {items.map((e) => (
          <li key={e.id} data-enquiry-id={e.id}>
            <button
              type="button"
              className="pq-btn pq-btn-ghost"
              data-testid={`inbox-open-${e.id}`}
              onClick={() => onOpen(e.id)}
              style={{ display: "flex", justifyContent: "space-between", gap: 12, width: "100%", textAlign: "left", padding: "0.7rem 1rem" }}
            >
              <span>{firstLine(e)}</span>
              <span className="pq-chip">{e.status.replace(/_/g, " ")}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
