"use client";

import { useState, type JSX } from "react";

import type { ApiError } from "@/lib/api";
import type { F60Request, F60Result, MissingStatus } from "@/lib/features/f60_missing_parts_queue";

// F60 Missing-parts queue — assigned staff set a status with a note. Resolving requires a note
// (the Resolve action is disabled until one is typed). Submits only typed identifiers. States:
// loading / empty / error / updated.
const STATUSES: MissingStatus[] = ["investigating", "resolved", "unavailable"];

export function MissingPartsQueue(props: {
  value: F60Result | null;
  loading: boolean;
  error: ApiError | null;
  onAction: (request: F60Request) => Promise<void>;
  itemId?: string;
  expectedRevision?: number;
}): JSX.Element {
  const { value, loading, error, onAction, itemId, expectedRevision } = props;
  const [status, setStatus] = useState<MissingStatus>("investigating");
  const [note, setNote] = useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!itemId) return;
    await onAction({ item_id: itemId, status, staff_note: note, expected_revision: expectedRevision ?? 1 });
  }

  const resolveBlocked = status === "resolved" && !note.trim();

  return (
    <section aria-label="Missing parts queue" data-testid="missing-parts-queue">
      <form onSubmit={submit}>
        <label>
          Status
          <select value={status} onChange={(e) => setStatus(e.target.value as MissingStatus)}>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <label>
          Staff note
          <textarea value={note} onChange={(e) => setNote(e.target.value)} />
        </label>
        <button type="submit" disabled={loading || resolveBlocked || !itemId}>
          {loading ? "Saving…" : "Update"}
        </button>
        {resolveBlocked ? <p role="note">Resolving requires an explanation.</p> : null}
      </form>

      {error ? (
        <p role="alert">
          {error.message}
          {error.requestId ? ` (ref ${error.requestId})` : ""}
        </p>
      ) : null}
      {value === null && !loading && !error ? (
        <p data-testid="missing-empty">No update yet.</p>
      ) : null}
      {value !== null ? (
        <p role="status" data-testid="missing-updated">
          Status is now {value.status}.
        </p>
      ) : null}
    </section>
  );
}
