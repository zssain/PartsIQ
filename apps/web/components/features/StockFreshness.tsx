"use client";

import { useState, type JSX } from "react";

import type { ApiError } from "@/lib/api";
import type { F35Request, F35Result } from "@/lib/features/f35_stock_freshness";

// F35 Stock freshness — shows the reviewer whether the plan's stock snapshot is still fresh,
// and which items changed. Re-check submits only the enquiry id + revision (the server reads
// current stock). Stale stock is shown as a warning, never a delivery guarantee.
export function StockFreshness(props: {
  value: F35Result | null;
  loading: boolean;
  error: ApiError | null;
  onAction: (request: F35Request) => Promise<void>;
  enquiryId?: string;
  expectedRevision?: number;
}): JSX.Element {
  const { value, loading, error, onAction, enquiryId, expectedRevision } = props;
  const [busy, setBusy] = useState(false);

  async function recheck() {
    if (!enquiryId) return;
    setBusy(true);
    try {
      await onAction({ enquiry_id: enquiryId, expected_revision: expectedRevision ?? 1 });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-label="Stock freshness" data-testid="stock-freshness">
      <button type="button" onClick={recheck} disabled={busy || loading || !enquiryId}>
        {busy || loading ? "Checking…" : "Re-check stock"}
      </button>
      {error ? (
        <p role="alert">
          {error.message}
          {error.requestId ? ` (ref ${error.requestId})` : ""}
        </p>
      ) : null}
      {value === null && !loading && !error ? (
        <p data-testid="freshness-empty">Stock freshness not checked yet.</p>
      ) : null}
      {value !== null ? (
        value.fresh ? (
          <p role="status" data-testid="freshness-fresh">
            Stock is current as of {new Date(value.checked_at).toLocaleString()}.
          </p>
        ) : (
          <p role="alert" data-testid="freshness-stale">
            Stock changed or is stale for {value.changed_item_ids.length} item(s) — re-plan before approving. This is
            not a delivery guarantee.
          </p>
        )
      ) : null}
    </section>
  );
}
