"use client";

import { useCallback, useState, type JSX } from "react";

import { ApiError } from "@/lib/api";
import { ImportWizard } from "@/components/features/ImportWizard";
import { getReport, requestValidate, type F58Request, type F58Result } from "@/lib/features/f58_catalogue_imports";

// F58 staff route: run a dry-run validation on an import batch and show its report. Validation
// is queued to the worker; the report is then fetched. Admin role is enforced by the gateway.
export default function StaffImportsPage(): JSX.Element {
  const [value, setValue] = useState<F58Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const run = useCallback(async (request: F58Request) => {
    setLoading(true);
    setError(null);
    try {
      await requestValidate(request.batch_id);
      setValue(await getReport(request.batch_id));
    } catch (err) {
      setError(err instanceof ApiError ? err : null);
    } finally {
      setLoading(false);
    }
  }, []);

  return (
    <div className="pq-container" style={{ paddingTop: 40, paddingBottom: 40 }}>
      <span className="pq-badge" style={{ marginBottom: 12 }}>Staff · imports · admin</span>
      <h1 style={{ fontSize: "clamp(1.7rem, 4vw, 2.6rem)", fontWeight: 800 }}>Catalogue imports</h1>
      <p className="pq-muted" style={{ marginTop: 10, marginBottom: 20, maxWidth: 620 }}>
        Dry-run validation reads CSV/XLSX without evaluating formulas, rejects macros, and checks schema, references,
        serial overlap, supersession cycles and source evidence — before anything is published.
      </p>
      <div className="pq-card" style={{ padding: 20 }}>
        <ImportWizard value={value} loading={loading} error={error} onAction={run} />
      </div>
    </div>
  );
}
