"use client";

import type { JSX } from "react";

import type { EnquiryView } from "@/lib/contracts";

// Review timeline (F18). Shows the persisted stages reached (derived from the real status),
// the current wait reason split into customer vs staff, and the last update; a failed refresh
// retains the last state and offers retry. No stage is ever shown as complete unless the
// server state reached it.
const STAGES = ["received", "processing", "awaiting_review", "approved"] as const;
const REACHED_BY: Record<string, number> = {
  received: 0,
  processing: 1,
  needs_information: 1,
  awaiting_review: 2,
  approved: 3,
  rejected: 2,
  failed: 1,
};

export function Timeline({
  enquiry,
  lastUpdated,
  pollFailed,
  onRetry,
}: {
  enquiry: EnquiryView | null;
  lastUpdated: string | null;
  pollFailed: boolean;
  onRetry: () => void;
}): JSX.Element {
  if (enquiry === null) {
    return <p data-testid="timeline-empty">No status yet.</p>;
  }
  const reached = REACHED_BY[enquiry.status] ?? 0;
  const wait =
    enquiry.status === "needs_information"
      ? "Waiting for the customer"
      : enquiry.status === "awaiting_review"
        ? "Waiting for staff review"
        : null;

  return (
    <aside aria-label="Timeline" data-testid="timeline">
      <ol>
        {STAGES.map((stage, index) => (
          <li key={stage} data-reached={index <= reached ? "true" : "false"}>
            {stage}
          </li>
        ))}
      </ol>
      {wait ? <p data-testid="wait-reason">{wait}</p> : null}
      {lastUpdated ? <p data-testid="last-updated">Last updated: {lastUpdated}</p> : null}
      {pollFailed ? (
        <p role="alert">
          Status refresh failed.{" "}
          <button type="button" onClick={onRetry}>
            Retry
          </button>
        </p>
      ) : null}
    </aside>
  );
}
