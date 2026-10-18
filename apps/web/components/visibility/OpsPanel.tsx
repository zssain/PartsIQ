"use client";

import { useCallback, useEffect, useState, type JSX } from "react";

import { ApiError } from "@/lib/api";
import { getMetrics, type OpsMetrics } from "@/lib/live";

// OpsPanel (visibility panel 4). Measured operations: per-stage latency, token usage, retries and
// remaining confirmed allowance from GET /v1/staff/metrics. A demo caller is role-denied offline
// (403/404/503) — that renders an HONEST empty state ("Metrics require a signed-in staff session /
// live backend"); numbers are NEVER fabricated. Any single field the backend did not measure reads
// "not measured" rather than zero. Honest states: loading / empty / error+retry / permission.

const PERMISSION = new Set([401, 403, 404]);
// Offline/role-denied in fixture mode commonly surfaces as a dependency being unavailable too.
const OFFLINE_STATUS = new Set([503]);

function num(value: number | null): string {
  return value === null ? "not measured" : String(value);
}

function ms(value: number | null): string {
  return value === null ? "not measured" : `${value} ms`;
}

export function OpsPanel(): JSX.Element {
  const [metrics, setMetrics] = useState<OpsMetrics | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setMetrics(await getMetrics());
    } catch (err) {
      if (err instanceof ApiError) setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading && metrics === null) {
    return (
      <section aria-label="Operations" data-testid="ops-panel" className="pq-card">
        <p data-testid="ops-loading">Loading operations metrics…</p>
      </section>
    );
  }

  // Role-denied (demo caller) OR backend offline → one honest empty state. No fabricated numbers.
  if (error && (PERMISSION.has(error.status) || OFFLINE_STATUS.has(error.status))) {
    return (
      <section aria-label="Operations" data-testid="ops-panel" className="pq-card">
        <p data-testid="ops-empty">
          Metrics require a signed-in staff session and a live backend. No operational data is
          available in the offline fixture demo.
          {error.requestId ? ` (ref ${error.requestId})` : ""}
        </p>
      </section>
    );
  }

  if (error) {
    return (
      <section aria-label="Operations" data-testid="ops-panel" className="pq-card">
        <p role="alert">
          Could not load operations metrics. {error.message}
          {error.requestId ? ` (ref ${error.requestId})` : ""}
        </p>
        <button type="button" onClick={() => void load()} data-testid="ops-retry">
          Retry
        </button>
      </section>
    );
  }

  if (metrics === null) {
    return (
      <section aria-label="Operations" data-testid="ops-panel" className="pq-card">
        <p data-testid="ops-empty">
          Metrics require a signed-in staff session and a live backend.
        </p>
      </section>
    );
  }

  return (
    <section aria-label="Operations" data-testid="ops-panel" className="pq-card">
      <h2 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: 10 }}>Operations</h2>
      <dl style={{ margin: 0 }}>
        <dt>Token usage</dt>
        <dd data-testid="ops-tokens">{num(metrics.tokens_used)}</dd>
        <dt>Retries</dt>
        <dd data-testid="ops-retries">{num(metrics.retries)}</dd>
        <dt>Remaining confirmed allowance</dt>
        <dd data-testid="ops-allowance">{num(metrics.remaining_allowance)}</dd>
      </dl>

      <h3 style={{ fontSize: "0.95rem", fontWeight: 700, marginTop: 14 }}>Stage latency</h3>
      {metrics.stages.length === 0 ? (
        <p data-testid="ops-stages-empty">No per-stage latency measured.</p>
      ) : (
        <ul data-testid="ops-stages" style={{ listStyle: "none", padding: 0, margin: 0 }}>
          {metrics.stages.map((s) => (
            <li key={s.stage} data-stage={s.stage} style={{ display: "flex", gap: 12, padding: "4px 0" }}>
              <span style={{ fontWeight: 600 }}>{s.stage}</span>
              <span className="pq-muted">p50 {ms(s.p50_ms)}</span>
              <span className="pq-muted">p95 {ms(s.p95_ms)}</span>
            </li>
          ))}
        </ul>
      )}
      {metrics.updated_at ? (
        <p className="pq-muted" style={{ fontSize: "0.8rem", marginTop: 10 }}>
          Measured {metrics.updated_at}
        </p>
      ) : null}
    </section>
  );
}
