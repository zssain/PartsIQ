"use client";

import { useCallback, useEffect, useState, type JSX } from "react";

import { ApiError } from "@/lib/api";
import { approveReview, getWorkspace, rejectReview, type ReviewView } from "@/lib/live";

// LIVE review workspace (F03 reviewer view, visibility panel 3 — ReviewSeparation shape). Keeps the
// three concerns structurally distinct:
//   1. AI suggestion     — the model's draft reply slots (greeting/explanation/closing): a SUGGESTION.
//   2. Database evidence — the VERIFIED facts (part_number, source_reference, allocations): the truth.
//   3. Human decision    — Approve / Reject-with-reason, the only place a decision is committed.
// After a decision we RE-FETCH the authoritative workspace (never optimistically show approval). On
// 409 we PRESERVE input and show "data changed — reload". A foreign id → 404 → "not available".
// Honest states: loading / empty / error+retry / permission, each surfacing the request id.

const PERMISSION = new Set([401, 403]);

export function ReviewWorkspaceLive({
  enquiryId,
  onBack,
}: {
  enquiryId: string;
  onBack: () => void;
}): JSX.Element {
  const [view, setView] = useState<ReviewView | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);

  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [decisionError, setDecisionError] = useState<string | null>(null);
  const [stale, setStale] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setView(await getWorkspace(enquiryId));
      setStale(false);
    } catch (err) {
      if (err instanceof ApiError) setError(err);
    } finally {
      setLoading(false);
    }
  }, [enquiryId]);

  useEffect(() => {
    void load();
  }, [load]);

  const decide = useCallback(
    async (action: "approve" | "reject") => {
      if (!view) return;
      if (action === "reject" && reason.trim().length === 0) {
        setDecisionError("A rejection reason is required.");
        return;
      }
      setBusy(true);
      setDecisionError(null);
      try {
        const revision = view.enquiry.revision;
        if (action === "approve") {
          await approveReview(enquiryId, revision);
        } else {
          await rejectReview(enquiryId, revision, reason.trim());
        }
        // Re-fetch the authoritative resource — never optimistically render the decision.
        await load();
      } catch (err) {
        if (err instanceof ApiError && err.status === 409) {
          // Concurrent change: PRESERVE input (reason stays), force an explicit reload.
          setStale(true);
          setDecisionError(
            `Data changed — reload before deciding.${err.requestId ? ` (ref ${err.requestId})` : ""}`,
          );
        } else {
          setDecisionError(
            err instanceof ApiError
              ? `${err.message}${err.requestId ? ` (ref ${err.requestId})` : ""}`
              : "Could not record the decision.",
          );
        }
      } finally {
        setBusy(false);
      }
    },
    [view, reason, enquiryId, load],
  );

  const BackButton = (
    <button type="button" className="pq-btn pq-btn-ghost" onClick={onBack} data-testid="review-back" style={{ marginBottom: 12 }}>
      ← Back to inbox
    </button>
  );

  if (loading && view === null) {
    return (
      <section aria-label="Review workspace" data-testid="review-workspace" className="pq-card">
        {BackButton}
        <p data-testid="workspace-loading">Loading the review…</p>
      </section>
    );
  }

  if (error && PERMISSION.has(error.status)) {
    return (
      <section aria-label="Review workspace" data-testid="review-workspace" className="pq-card">
        {BackButton}
        <p data-testid="workspace-permission">
          Reviewing requires a signed-in staff session.{error.requestId ? ` (ref ${error.requestId})` : ""}
        </p>
      </section>
    );
  }

  if (error && error.status === 404) {
    return (
      <section aria-label="Review workspace" data-testid="review-workspace" className="pq-card">
        {BackButton}
        <p data-testid="workspace-not-available">
          This enquiry is not available.{error.requestId ? ` (ref ${error.requestId})` : ""}
        </p>
      </section>
    );
  }

  if (error && view === null) {
    return (
      <section aria-label="Review workspace" data-testid="review-workspace" className="pq-card">
        {BackButton}
        <p role="alert">
          Could not load the review. {error.message}
          {error.requestId ? ` (ref ${error.requestId})` : ""}
        </p>
        <button type="button" className="pq-btn pq-btn-ghost" onClick={() => void load()} data-testid="workspace-retry">
          Retry
        </button>
      </section>
    );
  }

  if (view === null) {
    return (
      <section aria-label="Review workspace" data-testid="review-workspace" className="pq-card">
        {BackButton}
        <p data-testid="workspace-empty">Nothing to review yet.</p>
      </section>
    );
  }

  const draft = view.draft;
  const facts = view.facts;
  const status = view.enquiry.status;
  const decided = status === "approved" || status === "rejected";
  const canDecide = status === "awaiting_review" && !busy && !stale && !decided;

  return (
    <section aria-label="Review workspace" data-testid="review-workspace" className="pq-card">
      {BackButton}

      {/* REGION 1 — AI suggestion */}
      <article aria-label="AI suggestion" data-testid="region-ai-suggestion" style={{ borderLeft: "3px solid var(--pq-accent, #7c5cff)", paddingLeft: 12, marginBottom: 16 }}>
        <h2 style={{ fontSize: "1rem", fontWeight: 700 }}>AI suggestion</h2>
        <p className="pq-muted" style={{ fontSize: "0.8rem" }}>Proposed by the model — a suggestion, not a decision.</p>
        {draft === null ? (
          <p data-testid="ai-draft-empty">No draft suggested yet.</p>
        ) : (
          <div data-testid="ai-draft">
            <p>{draft.greeting}</p>
            <p>{draft.explanation}</p>
            <p>{draft.closing}</p>
          </div>
        )}
      </article>

      {/* REGION 2 — Database evidence */}
      <article aria-label="Database evidence" data-testid="region-database-evidence" style={{ borderLeft: "3px solid var(--pq-ink-soft, #4ea1ff)", paddingLeft: 12, marginBottom: 16 }}>
        <h2 style={{ fontSize: "1rem", fontWeight: 700 }}>Database evidence</h2>
        <p className="pq-muted" style={{ fontSize: "0.8rem" }}>What the catalogue and stock records actually say.</p>
        {!facts || facts.items.length === 0 ? (
          <p data-testid="evidence-empty">No verified facts loaded.</p>
        ) : (
          <ul data-testid="evidence-rows" style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {facts.items.map((item, i) => (
              <li key={`${item.part_number}:${i}`} data-testid="evidence-item" style={{ padding: "6px 0" }}>
                <strong>{item.part_number}</strong> — {item.name_en} (requested {item.requested_quantity})
                <div className="pq-muted" data-testid="evidence-source" style={{ fontSize: "0.85rem" }}>
                  {item.source_reference ? `Source: ${item.source_reference}` : "Evidence unavailable"}
                </div>
                <ul style={{ margin: "4px 0 0" }}>
                  {item.allocations.map((a, j) => (
                    <li key={`${a.warehouse_id}:${j}`} data-testid="evidence-allocation" style={{ fontSize: "0.85rem" }}>
                      Warehouse {a.warehouse_id}: {a.quantity} units · transfer ~{a.transfer_days}d (estimate, not guaranteed)
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        )}
      </article>

      {/* REGION 3 — Human decision */}
      <article aria-label="Human decision" data-testid="region-human-decision" style={{ borderLeft: "3px solid var(--pq-ok, #2bb673)", paddingLeft: 12 }}>
        <h2 style={{ fontSize: "1rem", fontWeight: 700 }}>Human decision</h2>
        <p className="pq-muted" style={{ fontSize: "0.8rem" }}>A person decides. The AI never publishes on its own.</p>

        {decided ? (
          <p data-testid="decision-outcome">Decision recorded: {status}.</p>
        ) : (
          <div style={{ display: "grid", gap: 10 }}>
            <button
              type="button"
              className="pq-btn pq-btn-primary"
              onClick={() => void decide("approve")}
              disabled={!canDecide}
              data-testid="approve"
            >
              {busy ? "Working…" : "Approve"}
            </button>
            <label style={{ display: "grid", gap: 4 }}>
              <span style={{ fontSize: "0.85rem" }}>Rejection reason</span>
              <textarea
                data-testid="reject-reason"
                aria-label="Rejection reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                rows={2}
                style={{ width: "100%", padding: 8, borderRadius: 8 }}
              />
            </label>
            <button
              type="button"
              className="pq-btn pq-btn-ghost"
              onClick={() => void decide("reject")}
              disabled={busy || stale}
              data-testid="reject"
            >
              Reject
            </button>
          </div>
        )}

        {stale ? (
          <button type="button" className="pq-btn pq-btn-ghost" onClick={() => void load()} data-testid="workspace-reload" style={{ marginTop: 10 }}>
            Reload
          </button>
        ) : null}

        {decisionError ? (
          <p role="alert" data-testid="decision-error" style={{ marginTop: 8 }}>
            {decisionError}
          </p>
        ) : null}
      </article>
    </section>
  );
}
