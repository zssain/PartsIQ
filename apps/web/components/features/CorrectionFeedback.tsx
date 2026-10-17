"use client";

import { useState, type JSX } from "react";

import type { ApiError } from "@/lib/api";
import type { F65Request, F65Result } from "@/lib/features/f65_correction_feedback";

// F65 Correction feedback (admin) — curate a reviewed correction into an anonymized labelled
// eval case. Submits only the correction id, a case id and the controlled expected label; no
// private customer text is ever sent. States: loading / empty / error / success.
export function CorrectionFeedback(props: {
  value: F65Result | null;
  loading: boolean;
  error: ApiError | null;
  onAction: (request: F65Request) => Promise<void>;
  correctionId?: string;
}): JSX.Element {
  const { value, loading, error, onAction, correctionId } = props;
  const [caseId, setCaseId] = useState("");
  const [expected, setExpected] = useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!correctionId || !caseId.trim() || !expected.trim()) return;
    await onAction({ correction_id: correctionId, case_id: caseId, approved_expected: expected });
  }

  return (
    <section aria-label="Correction feedback" data-testid="correction-feedback">
      <form onSubmit={submit}>
        <label>
          Case id
          <input value={caseId} onChange={(e) => setCaseId(e.target.value)} />
        </label>
        <label>
          Expected label (e.g. compatible:VP-10)
          <input value={expected} onChange={(e) => setExpected(e.target.value)} />
        </label>
        <button type="submit" disabled={loading || !correctionId}>
          {loading ? "Saving…" : "Curate eval case"}
        </button>
      </form>

      {error ? (
        <p role="alert">
          {error.message}
          {error.requestId ? ` (ref ${error.requestId})` : ""}
        </p>
      ) : null}
      {value === null && !loading && !error ? (
        <p data-testid="feedback-empty">No eval case curated yet.</p>
      ) : null}
      {value !== null ? (
        <p role="status" data-testid="case-curated">
          Eval case {value.case_id} curated from revision {value.source_revision}.
        </p>
      ) : null}
    </section>
  );
}
