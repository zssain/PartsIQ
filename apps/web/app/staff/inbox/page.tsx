"use client";

import { useEffect, useState, type JSX } from "react";

import { api } from "@/lib/api";
import type { EnquiryView } from "@/lib/contracts";

// Staff inbox shell (prompt 20). Lists the enquiries the signed-in reviewer may act on
// (assigned-only for real enquiries; own session for demo — enforced server-side). Rich
// filters/overdue indicators are layered by F36/F43.
export default function InboxPage(): JSX.Element {
  const [items, setItems] = useState<EnquiryView[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<EnquiryView[]>("/v1/staff/inbox")
      .then(setItems)
      .catch(() => setError("Could not load the inbox."));
  }, []);

  if (error) return <p role="alert">{error}</p>;
  if (items === null) return <p>Loading inbox…</p>;

  return (
    <main>
      <h1>Review inbox</h1>
      {items.length === 0 ? (
        <p data-testid="inbox-empty">No enquiries assigned to you.</p>
      ) : (
        <ul>
          {items.map((e) => (
            <li key={e.id}>
              <a href={`/staff/enquiries/${e.id}`}>
                {e.id} — {e.status} (rev {e.revision})
              </a>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
