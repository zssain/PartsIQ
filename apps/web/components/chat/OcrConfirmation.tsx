"use client";

import { useState, type JSX } from "react";

import type { ConfirmExtraction, NameplateResult } from "@/lib/contracts";

// Shows the extracted identifiers beside the nameplate and requires the user to confirm or
// correct them (F15, ADR-013). The serial is a plain text input so leading zeros survive
// exactly; a blank corrected serial is allowed and routes to the missing-serial flow
// server-side. extractionId/expectedRevision are plumbing the printed contract omits but the
// ConfirmExtraction payload requires; `extraction` and `onConfirm` match the contract.
export function OcrConfirmation({
  extraction,
  extractionId,
  expectedRevision,
  onConfirm,
}: {
  extraction: NameplateResult;
  extractionId: string;
  expectedRevision: number;
  onConfirm: (value: ConfirmExtraction) => Promise<void>;
}): JSX.Element {
  const [model, setModel] = useState(extraction.model_text ?? "");
  const [serial, setSerial] = useState(extraction.serial_text ?? "");
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      await onConfirm({
        extraction_id: extractionId,
        expected_revision: expectedRevision,
        model_text: model,
        serial_text: serial,
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-label="Confirm nameplate details">
      <img src={`/api/attachments/${extraction.attachment_id}/preview`} alt="Nameplate photo" style={{ maxWidth: 240 }} />
      {extraction.issues.length > 0 ? (
        <p role="note">Some fields were hard to read: {extraction.issues.join(", ")}. Please check them.</p>
      ) : null}
      <form onSubmit={submit}>
        <label>
          Model
          <input value={model} onChange={(e) => setModel(e.target.value)} />
        </label>
        <label>
          Serial
          {/* plain text; do not trim or normalise — leading zeros are significant */}
          <input value={serial} onChange={(e) => setSerial(e.target.value)} inputMode="text" />
        </label>
        <button type="submit" disabled={busy}>
          {busy ? "Confirming…" : "Confirm"}
        </button>
      </form>
    </section>
  );
}
