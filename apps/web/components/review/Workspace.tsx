"use client";

import { useCallback, useEffect, useRef, useState, type JSX } from "react";

import { api } from "@/lib/api";
import type { CandidateView, ReviewView } from "@/lib/contracts";
import { ApprovalControls } from "@/components/review/ApprovalControls";
import { Timeline } from "@/components/review/Timeline";

// Review workspace (F37, F27, F32). Assembles the CURRENT review snapshot: revision badge,
// items/candidates with evidence-derived match explanations, warehouse stock (available =
// on_hand − reserved, with warehouse and timestamp), the draft, the named verification
// results, the timeline, and staff-only notes kept separate from customer messages. Missing
// panels show explicit empty states; a candidate with no evidence is shown as unavailable
// rather than fabricated. Scores are labelled a "match score", never a calibrated confidence.
interface WorkspacePayload {
  review: ReviewView;
  candidates: CandidateView[];
  notes: string[];
}

export function Workspace({ enquiryId }: { enquiryId: string }): JSX.Element {
  const [data, setData] = useState<WorkspacePayload | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Results are applied only if the request is still current (no update after unmount/reload).
  const generation = useRef(0);
  const load = useCallback(() => {
    const mine = ++generation.current;
    return api<WorkspacePayload>(`/v1/staff/enquiries/${enquiryId}/workspace`).then(
      (payload) => {
        if (mine !== generation.current) return;
        setData(payload);
        setLoadError(null);
      },
      () => {
        if (mine === generation.current) setLoadError("Could not load the workspace.");
      },
    );
  }, [enquiryId]);

  useEffect(() => {
    void load();
    return () => { generation.current += 1; };
  }, [load]);

  if (loadError) {
    return <p role="alert">{loadError}</p>;
  }
  if (data === null) {
    return <p data-testid="workspace-loading">Loading…</p>;
  }

  const { review, candidates, notes } = data;

  return (
    <div className="pq-review-workspace">
      <ApprovalControls review={review} onChanged={load} />

      <Timeline enquiry={review.enquiry} lastUpdated={review.enquiry.updated_at} pollFailed={false} onRetry={load} />

      <section aria-label="Candidates">
        <h2>Candidates</h2>
        {candidates.length === 0 ? (
          <p data-testid="candidates-empty">No candidates yet.</p>
        ) : (
          <ul>
            {candidates.map((c) => (
              <li key={`${c.item_id}:${c.part_id}`}>
                <span>{c.part_number}</span> — <span>{c.name_en}</span>
                <span data-testid="match-score"> Match score: {c.score.toFixed(2)}</span>
                <p data-testid="explanation">
                  {c.reasons.length > 0 ? c.reasons.join(", ") : "No match reasons recorded."}
                </p>
                <p data-testid="evidence">
                  {c.source_reference ? `Evidence: ${c.source_reference}` : "Evidence unavailable"}
                </p>
                <ul>
                  {c.stock.map((s) => (
                    <li key={`${s.part_id}:${s.warehouse_id}`} data-testid="stock-row">
                      Warehouse {s.warehouse_id}: {s.available} available (as of {s.updated_at})
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-label="Verification">
        <h2>Verification</h2>
        {review.verification === null ? (
          <p data-testid="verification-empty">Not verified yet.</p>
        ) : review.verification.passed ? (
          <p data-testid="verification-passed">All checks passed.</p>
        ) : (
          <ul data-testid="verification-failures">
            {review.verification.failures.map((f, i) => (
              <li key={`${f.code}:${i}`}>
                {f.code}: {f.detail}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-label="Draft">
        <h2>Draft reply</h2>
        {review.draft === null ? <p data-testid="draft-empty">No draft yet.</p> : <p>{review.draft.explanation}</p>}
      </section>

      <section aria-label="Internal notes">
        <h2>Internal notes (staff only)</h2>
        {notes.length === 0 ? (
          <p data-testid="notes-empty">No internal notes.</p>
        ) : (
          <ul>
            {notes.map((n, i) => (
              <li key={i}>{n}</li>
            ))}
          </ul>
        )}
      </section>

      <section aria-label="Customer messages">
        <h2>Customer conversation</h2>
        <ul>
          {review.enquiry.messages.map((m) => (
            <li key={m.id} data-kind={m.kind}>
              {m.body}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
