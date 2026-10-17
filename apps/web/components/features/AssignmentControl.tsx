"use client";

import { useState, type JSX } from "react";

import type { ApiError } from "@/lib/api";
import type { F42Request, F42Result } from "@/lib/features/f42_assignments";

// F42 Assignment control (admin) — assign a reviewer by id, or clear to unassign. Submits only
// the typed assignee id (or null) + expected revision + idempotency key. States: loading /
// empty / error / success.
export function AssignmentControl(props: {
  value: F42Result | null;
  loading: boolean;
  error: ApiError | null;
  onAction: (request: F42Request) => Promise<void>;
  enquiryId?: string;
  expectedRevision?: number;
}): JSX.Element {
  const { value, loading, error, onAction, enquiryId, expectedRevision } = props;
  const [assignee, setAssignee] = useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!enquiryId) return;
    await onAction({
      enquiry_id: enquiryId,
      assigned_to: assignee.trim() || null,
      expected_revision: expectedRevision ?? 1,
      idempotency_key: crypto.randomUUID(),
    });
  }

  return (
    <section aria-label="Assignment" data-testid="assignment-control">
      <form onSubmit={submit}>
        <label>
          Reviewer id (blank to unassign)
          <input value={assignee} onChange={(e) => setAssignee(e.target.value)} />
        </label>
        <button type="submit" disabled={loading || !enquiryId}>
          {loading ? "Saving…" : "Assign"}
        </button>
      </form>

      {error ? (
        <p role="alert">
          {error.message}
          {error.requestId ? ` (ref ${error.requestId})` : ""}
        </p>
      ) : null}
      {value === null && !loading && !error ? (
        <p data-testid="assignment-empty">Not assigned yet.</p>
      ) : null}
      {value !== null ? (
        <p role="status" data-testid="assignment-set">
          {value.assigned_to ? `Assigned to ${value.assigned_to}` : "Unassigned"} at{" "}
          {new Date(value.assigned_at).toLocaleString()}.
        </p>
      ) : null}
    </section>
  );
}
