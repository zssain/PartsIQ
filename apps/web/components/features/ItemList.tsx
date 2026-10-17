"use client";

import { useState, type JSX } from "react";

import type { ApiError } from "@/lib/api";
import { canApproveAll, type F17Request, type F17Result, type ItemStatus } from "@/lib/features/f17_multi_part_enquiries";

// F17 Multi-part enquiries — lists each item with its independent status, candidate count and
// quantity, and surfaces the all-items readiness gate (one unresolved item blocks approval).
// The action re-resolves the current revision; it submits only typed identifiers.
const STATUS_LABEL: Record<ItemStatus, string> = {
  unresolved: "Not identified yet",
  needs_information: "Needs more information",
  ready: "Ready",
  unavailable: "Out of stock",
};

export function ItemList(props: {
  value: F17Result | null;
  loading: boolean;
  error: ApiError | null;
  onAction: (request: F17Request) => Promise<void>;
}): JSX.Element {
  const { value, loading, error, onAction } = props;
  const [busy, setBusy] = useState(false);

  async function refresh() {
    if (!value) return;
    setBusy(true);
    try {
      // Re-resolve from whatever item the server currently knows; identifiers only.
      const first = value.items[0];
      if (first) await onAction({ enquiry_id: first.id, expected_revision: 0 });
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <p data-testid="items-loading">Resolving items…</p>;
  if (error)
    return (
      <p role="alert">
        {error.message}
        {error.requestId ? ` (ref ${error.requestId})` : ""}
      </p>
    );
  if (value === null) return <p data-testid="items-empty">No items resolved yet.</p>;
  if (value.items.length === 0) return <p data-testid="items-empty">This enquiry has no items.</p>;

  return (
    <section aria-label="Enquiry items" data-testid="item-list">
      <ul>
        {value.items.map((item, index) => (
          <li key={item.id} data-status={item.status}>
            <span>Item {index + 1}</span>: {item.request.description}
            {item.request.quantity !== null ? <span> × {item.request.quantity}</span> : null}
            <span data-testid="item-status"> — {STATUS_LABEL[item.status]}</span>
            <span> ({item.candidate_part_ids.length} candidate(s))</span>
          </li>
        ))}
      </ul>
      {canApproveAll(value) ? (
        <p role="status" data-testid="all-items-ready">All items are ready for approval.</p>
      ) : (
        <p role="note" data-testid="items-blocked">
          {value.unresolved_item_ids.length} item(s) still need attention before approval.
        </p>
      )}
      <button type="button" onClick={refresh} disabled={busy}>
        {busy ? "Refreshing…" : "Refresh items"}
      </button>
    </section>
  );
}
