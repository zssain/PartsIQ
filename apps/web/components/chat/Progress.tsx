"use client";

import type { JSX } from "react";

import type { EnquiryView } from "@/lib/contracts";

// Progress timeline (F18). Renders only persisted server state — never a fabricated
// "completed" step — and separates "waiting for you" (the customer) from "waiting for our
// team" (staff review). The parent owns polling; this is a pure presentational view of the
// latest enquiry snapshot plus a retry affordance when a poll failed.
const WAITING_CUSTOMER = new Set(["needs_information"]);
const WAITING_STAFF = new Set(["awaiting_review"]);

export function Progress({
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
    return <p data-testid="progress-empty">Loading the latest status…</p>;
  }

  const waiting = WAITING_CUSTOMER.has(enquiry.status)
    ? "Waiting for you to reply"
    : WAITING_STAFF.has(enquiry.status)
      ? "Waiting for our team to review"
      : null;

  return (
    <aside aria-label="Progress" data-testid="progress">
      <p data-testid="progress-status">Status: {enquiry.status}</p>
      {waiting ? <p data-testid="wait-reason">{waiting}</p> : null}
      {lastUpdated ? <p data-testid="last-updated">Last updated: {lastUpdated}</p> : null}
      {pollFailed ? (
        <p role="alert">
          Could not refresh the status.{" "}
          <button type="button" onClick={onRetry}>
            Retry
          </button>
        </p>
      ) : null}
    </aside>
  );
}
