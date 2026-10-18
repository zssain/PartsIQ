"use client";

import { useCallback, useEffect, useState, type JSX } from "react";

import { ApiError } from "@/lib/api";
import type { CandidateView, ReviewView } from "@/lib/contracts";
import { api } from "@/lib/api";
import { approveEnquiry } from "@/lib/live";

// ReviewSeparation (visibility panel 3). Keeps the three concerns visibly, structurally distinct:
//   1. "AI suggestion"    — the model's proposed draft/candidates (clearly labelled as a suggestion)
//   2. "Database evidence" — the verified facts the suggestion must agree with (source references,
//                            stock) — NOT the model's opinion
//   3. "Human decision"    — the approve/reject control a person operates; approve → approveEnquiry
// The human-decision region is the only place a decision is committed, so a reader can always see
// what the AI proposed vs. what the database actually says vs. what a human chose. Honest states:
// loading / empty / error+retry / permission (401/403/404), each surfacing the request id.

interface ReviewPayload {
  review: ReviewView;
  candidates: CandidateView[];
}

const PERMISSION = new Set([401, 403, 404]);

export function ReviewSeparation({ enquiryId }: { enquiryId: string }): JSX.Element {
  const [data, setData] = useState<ReviewPayload | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const [decisionError, setDecisionError] = useState<ApiError | null>(null);
  const [decision, setDecision] = useState<ReviewView["enquiry"]["status"] | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await api<ReviewPayload>(`/v1/staff/enquiries/${enquiryId}/workspace`));
    } catch (err) {
      if (err instanceof ApiError) setError(err);
    } finally {
      setLoading(false);
    }
  }, [enquiryId]);

  useEffect(() => {
    void load();
  }, [load]);

  const approve = useCallback(async () => {
    setBusy(true);
    setDecisionError(null);
    try {
      const enquiry = await approveEnquiry(enquiryId);
      setDecision(enquiry.status);
    } catch (err) {
      if (err instanceof ApiError) setDecisionError(err);
    } finally {
      setBusy(false);
    }
  }, [enquiryId]);

  if (loading && data === null) {
    return (
      <section aria-label="Review separation" data-testid="review-separation" className="pq-card">
        <p data-testid="review-loading">Loading the review…</p>
      </section>
    );
  }

  if (error && PERMISSION.has(error.status)) {
    return (
      <section aria-label="Review separation" data-testid="review-separation" className="pq-card">
        <p data-testid="review-permission">
          Reviewing an enquiry requires a signed-in staff session.
          {error.requestId ? ` (ref ${error.requestId})` : ""}
        </p>
      </section>
    );
  }

  if (error) {
    return (
      <section aria-label="Review separation" data-testid="review-separation" className="pq-card">
        <p role="alert">
          Could not load the review. {error.message}
          {error.requestId ? ` (ref ${error.requestId})` : ""}
        </p>
        <button type="button" onClick={() => void load()} data-testid="review-retry">
          Retry
        </button>
      </section>
    );
  }

  if (data === null) {
    return (
      <section aria-label="Review separation" data-testid="review-separation" className="pq-card">
        <p data-testid="review-empty">Nothing to review yet.</p>
      </section>
    );
  }

  const { review, candidates } = data;
  const draft = review.draft;
  const status = decision ?? review.enquiry.status;
  const alreadyDecided = status === "approved" || status === "rejected";
  const canApprove = review.enquiry.status === "awaiting_review" && !busy && !alreadyDecided;

  return (
    <section aria-label="Review separation" data-testid="review-separation" className="pq-card">
      {/* REGION 1 — AI suggestion */}
      <article aria-label="AI suggestion" data-testid="region-ai-suggestion" style={{ borderLeft: "3px solid var(--pq-accent, #7c5cff)", paddingLeft: 12, marginBottom: 16 }}>
        <h2 style={{ fontSize: "1rem", fontWeight: 700 }}>AI suggestion</h2>
        <p className="pq-muted" style={{ fontSize: "0.8rem" }}>Proposed by the model — a suggestion, not a decision.</p>
        {draft === null ? (
          <p data-testid="ai-draft-empty">No draft suggested yet.</p>
        ) : (
          <p data-testid="ai-draft">{draft.explanation}</p>
        )}
        {candidates.length === 0 ? (
          <p data-testid="ai-candidates-empty">No candidate parts suggested.</p>
        ) : (
          <ul data-testid="ai-candidates">
            {candidates.map((c) => (
              <li key={`${c.item_id}:${c.part_id}`}>
                {c.part_number} — {c.name_en} <span className="pq-muted">(match score {c.score.toFixed(2)})</span>
              </li>
            ))}
          </ul>
        )}
      </article>

      {/* REGION 2 — Database evidence */}
      <article aria-label="Database evidence" data-testid="region-database-evidence" style={{ borderLeft: "3px solid var(--pq-ink-soft, #4ea1ff)", paddingLeft: 12, marginBottom: 16 }}>
        <h2 style={{ fontSize: "1rem", fontWeight: 700 }}>Database evidence</h2>
        <p className="pq-muted" style={{ fontSize: "0.8rem" }}>What the catalogue and stock records actually say.</p>
        {candidates.length === 0 ? (
          <p data-testid="evidence-empty">No evidence records loaded.</p>
        ) : (
          <ul data-testid="evidence-rows">
            {candidates.map((c) => (
              <li key={`${c.item_id}:${c.part_id}`}>
                <span data-testid="evidence-source">
                  {c.source_reference ? `Source: ${c.source_reference}` : "Evidence unavailable"}
                </span>
                <ul>
                  {c.stock.map((s) => (
                    <li key={`${s.part_id}:${s.warehouse_id}`} data-testid="evidence-stock">
                      Warehouse {s.warehouse_id}: {s.available} available (as of {s.updated_at})
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
        {alreadyDecided ? (
          <p data-testid="decision-outcome">Decision recorded: {status}.</p>
        ) : (
          <button
            type="button"
            className="pq-btn pq-btn-primary"
            onClick={() => void approve()}
            disabled={!canApprove}
            data-testid="approve"
          >
            {busy ? "Approving…" : "Approve"}
          </button>
        )}
        {decisionError ? (
          <p role="alert">
            Could not record the decision. {decisionError.message}
            {decisionError.requestId ? ` (ref ${decisionError.requestId})` : ""}
          </p>
        ) : null}
      </article>
    </section>
  );
}
