"use client";

import { useState, type JSX } from "react";

import { api, ApiError } from "@/lib/api";
import type { ReplySlots, ReviewView } from "@/lib/contracts";

// Review actions (F39, F53, F61). Approve is enabled ONLY for a current, verified draft; the
// request carries the expected revision and an idempotency key so a double-click publishes
// once, and a 409 forces a reload + an explicit fresh review. Prose edits go through the
// structured slot schema (re-verified server-side). Reject requires a reason. The approved
// PDF export is requested here and its queue status shown.
export function ApprovalControls({
  review,
  onChanged,
}: {
  review: ReviewView;
  onChanged: () => Promise<void>;
}): JSX.Element {
  const [busy, setBusy] = useState(false);
  const [stale, setStale] = useState(false);
  const [reason, setReason] = useState("");
  const [slots, setSlots] = useState<ReplySlots | null>(review.draft);
  const [error, setError] = useState<string | null>(null);
  const [exportState, setExportState] = useState<string | null>(null);

  const enquiry = review.enquiry;
  const verifiedCurrent = review.verification?.passed === true && enquiry.status === "awaiting_review";
  const canApprove = verifiedCurrent && !busy && !stale;

  async function handle(action: "approve" | "reject") {
    if (action === "reject" && reason.trim().length === 0) {
      setError("A rejection reason is required.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const body =
        action === "approve"
          ? { enquiry_id: enquiry.id, expected_revision: enquiry.revision, draft_id: null, edited_slots: slots }
          : { enquiry_id: enquiry.id, expected_revision: enquiry.revision, reason };
      await api(`/v1/enquiries/${enquiry.id}/${action}`, {
        method: "POST",
        headers: { "idempotency-key": crypto.randomUUID() },
        body: JSON.stringify(body),
      });
      await onChanged();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setStale(true); // concurrent change: require an explicit fresh review
        setError("This enquiry changed. Reload and review the current revision before approving.");
      } else {
        setError(err instanceof ApiError ? err.message : "Action failed.");
      }
    } finally {
      setBusy(false);
    }
  }

  async function exportPdf() {
    setExportState("queued");
    try {
      await api(`/v1/enquiries/${enquiry.id}/export`, {
        method: "POST",
        headers: { "idempotency-key": crypto.randomUUID() },
        body: JSON.stringify({ enquiry_id: enquiry.id, revision: enquiry.revision }),
      });
      setExportState("processing");
    } catch (err) {
      setExportState(null);
      setError(err instanceof ApiError ? err.message : "Could not queue the PDF.");
    }
  }

  return (
    <section aria-label="Review actions">
      <span data-testid="revision-badge">Revision {enquiry.revision}</span>

      {slots ? (
        <fieldset>
          <legend>Reply (structured)</legend>
          <input aria-label="Greeting" value={slots.greeting} onChange={(e) => setSlots({ ...slots, greeting: e.target.value })} />
          <textarea aria-label="Explanation" value={slots.explanation} onChange={(e) => setSlots({ ...slots, explanation: e.target.value })} />
          <input aria-label="Closing" value={slots.closing} onChange={(e) => setSlots({ ...slots, closing: e.target.value })} />
        </fieldset>
      ) : null}

      <button type="button" onClick={() => handle("approve")} disabled={!canApprove} data-testid="approve">
        Approve
      </button>

      <label>
        Rejection reason
        <textarea value={reason} onChange={(e) => setReason(e.target.value)} />
      </label>
      <button type="button" onClick={() => handle("reject")} disabled={busy} data-testid="reject">
        Reject
      </button>

      <button type="button" onClick={exportPdf} disabled={enquiry.status !== "approved"} data-testid="export-pdf">
        Download approved PDF
      </button>
      {exportState ? <span data-testid="export-state">PDF: {exportState}</span> : null}

      {error ? <p role="alert">{error}</p> : null}
    </section>
  );
}
