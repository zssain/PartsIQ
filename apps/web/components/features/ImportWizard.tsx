"use client";

import { useState, type JSX } from "react";

import type { ApiError } from "@/lib/api";
import type { F58Request, F58Result } from "@/lib/features/f58_catalogue_imports";

// F58 Import wizard — staff submit a batch id to run a dry-run validation and see the report
// (valid flag, row count, per-row errors) before any publish. Submits only the typed batch id;
// parsing/validation happen server-side in the worker. States: loading / empty / error / report.
export function ImportWizard(props: {
  value: F58Result | null;
  loading: boolean;
  error: ApiError | null;
  onAction: (request: F58Request) => Promise<void>;
}): JSX.Element {
  const { value, loading, error, onAction } = props;
  const [batchId, setBatchId] = useState("");

  async function validate(event: React.FormEvent) {
    event.preventDefault();
    if (!batchId.trim()) return;
    await onAction({ batch_id: batchId.trim() });
  }

  return (
    <section aria-label="Catalogue import" data-testid="import-wizard">
      <form onSubmit={validate}>
        <label>
          Import batch id
          <input value={batchId} onChange={(e) => setBatchId(e.target.value)} />
        </label>
        <button type="submit" disabled={loading}>
          {loading ? "Validating…" : "Validate (dry run)"}
        </button>
      </form>

      {error ? (
        <p role="alert">
          {error.message}
          {error.requestId ? ` (ref ${error.requestId})` : ""}
        </p>
      ) : null}
      {value === null && !loading && !error ? (
        <p data-testid="import-empty">Enter a batch id to validate it before publishing.</p>
      ) : null}
      {value !== null ? (
        <div data-testid="import-report" data-valid={value.valid}>
          <p role="status">
            {value.valid ? "Valid" : "Not valid"} — {value.row_count} rows.
          </p>
          {value.errors.length > 0 ? (
            <ul>
              {value.errors.map((issue, index) => (
                <li key={`${issue.code}-${issue.row ?? "file"}-${index}`}>
                  {issue.row !== null ? `Row ${issue.row}: ` : ""}
                  {issue.code} — {issue.detail}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
