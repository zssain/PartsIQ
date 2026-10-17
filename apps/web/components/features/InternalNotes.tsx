"use client";

import { useState, type JSX } from "react";

import type { ApiError } from "@/lib/api";
import type { F41Request, F41Result } from "@/lib/features/f41_internal_notes";

// F41 Internal notes — staff-only. Appends a note (author + timestamp) and shows the latest.
// React escapes the rendered body. Submit is disabled for an empty or over-limit note. These
// notes are never shown to a customer or in the PDF.
const MAX_NOTE = 4000;

export function InternalNotes(props: {
  value: F41Result | null;
  loading: boolean;
  error: ApiError | null;
  onAction: (request: F41Request) => Promise<void>;
  enquiryId?: string;
}): JSX.Element {
  const { value, loading, error, onAction, enquiryId } = props;
  const [body, setBody] = useState("");

  const invalid = !body.trim() || body.length > MAX_NOTE;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!enquiryId || invalid) return;
    await onAction({ enquiry_id: enquiryId, body, idempotency_key: crypto.randomUUID() });
    setBody("");
  }

  return (
    <section aria-label="Internal notes (staff only)" data-testid="internal-notes">
      <form onSubmit={submit}>
        <label>
          Reviewer note (not shown to the customer)
          <textarea value={body} onChange={(e) => setBody(e.target.value)} maxLength={MAX_NOTE} />
        </label>
        <button type="submit" disabled={loading || invalid || !enquiryId}>
          {loading ? "Saving…" : "Add note"}
        </button>
      </form>

      {error ? (
        <p role="alert">
          {error.message}
          {error.requestId ? ` (ref ${error.requestId})` : ""}
        </p>
      ) : null}
      {value === null && !loading && !error ? (
        <p data-testid="notes-empty">No internal notes yet.</p>
      ) : null}
      {value !== null ? (
        <p role="status" data-testid="note-added">
          {/* React escapes the body */}
          Note by {value.author_id} at {new Date(value.created_at).toLocaleString()}: {value.body}
        </p>
      ) : null}
    </section>
  );
}
