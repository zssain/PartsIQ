"use client";

import { useState, type JSX } from "react";

import type { ApiError } from "@/lib/api";
import type { F55Request, F55Result } from "@/lib/features/f55_saved_machines";

// F55 Saved machines — save a confirmed (model, serial) under a label for reuse. The form
// submits only typed identifiers; the model id comes from a confirmed identification, never
// authored freehand in the browser. States: loading / empty / error / saved.
export function SavedMachines(props: {
  value: F55Result | null;
  loading: boolean;
  error: ApiError | null;
  onAction: (request: F55Request) => Promise<void>;
}): JSX.Element {
  const { value, loading, error, onAction } = props;
  const [label, setLabel] = useState("");
  const [modelId, setModelId] = useState<number | "">("");
  const [serial, setSerial] = useState("");
  const [busy, setBusy] = useState(false);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!label.trim() || modelId === "" || !serial.trim()) return;
    setBusy(true);
    try {
      await onAction({
        label,
        model_id: Number(modelId),
        serial_text: serial, // verbatim — leading zeros are significant
        idempotency_key: crypto.randomUUID(),
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-label="Saved machines" data-testid="saved-machines">
      <form onSubmit={save}>
        <label>
          Label
          <input value={label} onChange={(e) => setLabel(e.target.value)} />
        </label>
        <label>
          Model id
          <input
            inputMode="numeric"
            value={modelId}
            onChange={(e) => setModelId(e.target.value === "" ? "" : Number(e.target.value))}
          />
        </label>
        <label>
          Serial
          <input value={serial} onChange={(e) => setSerial(e.target.value)} inputMode="text" />
        </label>
        <button type="submit" disabled={busy || loading}>
          {busy ? "Saving…" : "Save machine"}
        </button>
      </form>

      {loading ? <p data-testid="machines-loading">Saving…</p> : null}
      {error ? (
        <p role="alert">
          {error.message}
          {error.requestId ? ` (ref ${error.requestId})` : ""}
        </p>
      ) : null}
      {value === null && !loading && !error ? (
        <p data-testid="machines-empty">No machine saved yet.</p>
      ) : null}
      {value !== null ? (
        <p role="status" data-testid="machine-saved">
          Saved “{value.label}” (model {value.model_id}, serial {value.serial_text}).
        </p>
      ) : null}
    </section>
  );
}
