"use client";

import { type JSX } from "react";

import type { ApiError } from "@/lib/api";
import type { F29Request, F29Result } from "@/lib/features/f29_evidence_page_viewer";

// F29 Evidence viewer — opens the exact cited page of a (synthetic) compatibility document in a
// short-lived signed link. The reviewer clicks a citation; only the typed evidence id is sent.
// States: loading / empty / error / success. A customer never reaches this (they see the
// citation reference only).
export function EvidenceViewer(props: {
  value: F29Result | null;
  loading: boolean;
  error: ApiError | null;
  onAction: (request: F29Request) => Promise<void>;
  enquiryId?: string;
  evidenceId?: string;
  expectedRevision?: number;
}): JSX.Element {
  const { value, loading, error, onAction, enquiryId, evidenceId, expectedRevision } = props;

  async function open() {
    if (!enquiryId || !evidenceId) return;
    await onAction({ enquiry_id: enquiryId, evidence_id: evidenceId, expected_revision: expectedRevision ?? 1 });
  }

  return (
    <section aria-label="Evidence viewer" data-testid="evidence-viewer">
      <button type="button" onClick={open} disabled={loading || !evidenceId}>
        {loading ? "Opening…" : "Open cited evidence"}
      </button>
      {error ? (
        <p role="alert">
          {error.message}
          {error.requestId ? ` (ref ${error.requestId})` : ""}
        </p>
      ) : null}
      {value === null && !loading && !error ? (
        <p data-testid="evidence-empty">Select a citation to open its document page.</p>
      ) : null}
      {value !== null ? (
        <div data-testid="evidence-open">
          {value.synthetic ? <p role="note">Synthetic demonstration document.</p> : null}
          <a href={value.url} target="_blank" rel="noopener noreferrer">
            Open page {value.page_number}
          </a>
          <p>Link expires {new Date(value.expires_at).toLocaleString()}.</p>
        </div>
      ) : null}
    </section>
  );
}
