"use client";

import { useState, type JSX } from "react";

import type { ApiError } from "@/lib/api";
import type { F38Request, F38Result } from "@/lib/features/f38_correct_extracted_details";

// F38 Correction editor — a reviewer corrects the typed extracted fields of an item (model /
// serial here) with a reason. It submits only typed identifiers + the expected revision; it can
// never set a status or a candidate fact. States: loading / empty / error / success.
export function CorrectionEditor(props: {
  value: F38Result | null;
  loading: boolean;
  error: ApiError | null;
  onAction: (request: F38Request) => Promise<void>;
  enquiryId?: string;
  itemId?: string;
  expectedRevision?: number;
}): JSX.Element {
  const { value, loading, error, onAction, enquiryId, itemId, expectedRevision } = props;
  const [model, setModel] = useState("");
  const [serial, setSerial] = useState("");
  const [reason, setReason] = useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!enquiryId || !itemId || !reason.trim()) return;
    await onAction({
      enquiry_id: enquiryId,
      expected_revision: expectedRevision ?? 1,
      reason,
      corrections: [{ item_id: itemId, model_text: model || null, serial_text: serial || null }],
    });
  }

  return (
    <section aria-label="Correct extracted details" data-testid="correction-editor">
      <form onSubmit={submit}>
        <label>
          Model
          <input value={model} onChange={(e) => setModel(e.target.value)} />
        </label>
        <label>
          Serial
          {/* plain text — leading zeros are significant */}
          <input value={serial} onChange={(e) => setSerial(e.target.value)} inputMode="text" />
        </label>
        <label>
          Reason
          <input value={reason} onChange={(e) => setReason(e.target.value)} />
        </label>
        <button type="submit" disabled={loading || !reason.trim()}>
          {loading ? "Applying…" : "Apply correction"}
        </button>
      </form>

      {error ? (
        <p role="alert">
          {error.message}
          {error.requestId ? ` (ref ${error.requestId})` : ""}
        </p>
      ) : null}
      {value === null && !loading && !error ? (
        <p data-testid="correction-empty">Correct the model or serial, then re-run the review.</p>
      ) : null}
      {value !== null ? (
        <p role="status" data-testid="correction-applied">
          Correction applied — now at revision {value.enquiry.revision} ({value.enquiry.status}).
        </p>
      ) : null}
    </section>
  );
}
