"use client";

import { useState, type JSX } from "react";

import type { ApiError } from "@/lib/api";
import type { F59Request, F59Result } from "@/lib/features/f59_catalogue_versioning";

// F59 Catalogue versions (staff) — publish a validated candidate as the single active version.
// The expected-active id guards against two publishers racing. Submits only typed ids. The
// result (version/published_at/record_count) is produced by the worker once the queued publish
// completes; the component shows the known value when present.
export function CatalogueVersions(props: {
  value: F59Result | null;
  loading: boolean;
  error: ApiError | null;
  onAction: (request: F59Request) => Promise<void>;
  candidateVersionId?: string;
  activeVersionId?: string;
}): JSX.Element {
  const { value, loading, error, onAction, candidateVersionId, activeVersionId } = props;
  const [busy, setBusy] = useState(false);

  async function publish() {
    if (!candidateVersionId || !activeVersionId) return;
    setBusy(true);
    try {
      await onAction({
        version_id: candidateVersionId,
        expected_active_version_id: activeVersionId,
        idempotency_key: crypto.randomUUID(),
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-label="Catalogue versions" data-testid="catalogue-versions">
      <button type="button" onClick={publish} disabled={busy || loading || !candidateVersionId}>
        {busy || loading ? "Publishing…" : "Publish candidate version"}
      </button>
      {error ? (
        <p role="alert">
          {error.message}
          {error.requestId ? ` (ref ${error.requestId})` : ""}
        </p>
      ) : null}
      {value === null && !loading && !error ? (
        <p data-testid="versions-empty">No version published in this session yet.</p>
      ) : null}
      {value !== null ? (
        <p role="status" data-testid="version-published">
          Active version {value.version_id.slice(0, 8)} — {value.record_count} records.
        </p>
      ) : null}
    </section>
  );
}
