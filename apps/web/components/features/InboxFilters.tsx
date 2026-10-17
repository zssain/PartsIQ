"use client";

import { useState, type JSX } from "react";

import type { ApiError } from "@/lib/api";
import type { F36Request, F36Result } from "@/lib/features/f36_staff_inbox";

// F36 Inbox filters — status / priority / overdue / text filters over the staff inbox. Submits
// only typed filter identifiers; the access scope and counts are server-enforced. Shows the
// scoped total (never a global count). States: loading / empty / error / success.
export function InboxFilters(props: {
  value: F36Result | null;
  loading: boolean;
  error: ApiError | null;
  onAction: (request: F36Request) => Promise<void>;
}): JSX.Element {
  const { value, loading, error, onAction } = props;
  const [status, setStatus] = useState("");
  const [overdue, setOverdue] = useState(false);
  const [query, setQuery] = useState("");

  async function apply(event: React.FormEvent) {
    event.preventDefault();
    await onAction({ status: status || null, overdue, query: query || null });
  }

  return (
    <section aria-label="Inbox filters" data-testid="inbox-filters">
      <form onSubmit={apply}>
        <label>
          Status
          <input value={status} onChange={(e) => setStatus(e.target.value)} />
        </label>
        <label>
          Overdue only
          <input type="checkbox" checked={overdue} onChange={(e) => setOverdue(e.target.checked)} />
        </label>
        <label>
          Search
          <input value={query} onChange={(e) => setQuery(e.target.value)} />
        </label>
        <button type="submit" disabled={loading}>
          Apply
        </button>
      </form>

      {loading ? <p data-testid="inbox-loading">Loading inbox…</p> : null}
      {error ? (
        <p role="alert">
          {error.message}
          {error.requestId ? ` (ref ${error.requestId})` : ""}
        </p>
      ) : null}
      {value !== null ? (
        <>
          <p data-testid="scoped-total">{value.scoped_total} enquiry(ies) in your view.</p>
          {value.enquiries.length === 0 ? (
            <p data-testid="inbox-empty">No enquiries match those filters.</p>
          ) : (
            <ul>
              {value.enquiries.map((e) => (
                <li key={e.id}>
                  <a href={`/staff/enquiries/${e.id}`}>
                    {e.id.slice(0, 8)} — {e.status}
                  </a>
                </li>
              ))}
            </ul>
          )}
        </>
      ) : null}
    </section>
  );
}
