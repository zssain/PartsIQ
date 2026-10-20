"use client";

import { BarChart3 } from "lucide-react";
import type { JSX } from "react";

import { Alert, ErrorState, PageHeader, PermissionDenied, Skeleton } from "@/components/app/ui";
import { useLoad } from "@/lib/hooks";
import { useSession } from "@/lib/session";
import { ws } from "@/lib/workspace";

const fmt = (v: number | null | undefined, unit = "") => (v === null || v === undefined ? "Not measured" : `${Math.round(v * 10) / 10}${unit}`);

export default function AnalyticsPage(): JSX.Element {
  const { can } = useSession();
  const { data, error, loading, reload } = useLoad(() => ws.analytics());
  if (!can("analytics.read")) return <PermissionDenied />;
  return (
    <>
      <PageHeader title="Analytics" description="Counts and timings recorded by this workspace. Anything not measured is shown as such — never as zero." />
      {error ? <ErrorState error={error} onRetry={reload} /> : loading && !data ? <Skeleton lines={6} /> : data && (
        <>
          <Alert tone="info" title={data.scope === "demo" ? "Demo session scope" : "Account workspace scope"}>{data.scope_note}</Alert>
          <section className="app-section"><div className="app-grid cols-4" data-testid="analytics-stats">
            <Card label="Enquiries" value={String(data.enquiries.total)} />
            <Card label="Runs" value={String(data.runs.total)} />
            <Card label="Failed / blocked runs" value={String(data.runs.failed)} />
            <Card label="Retries" value={String(data.runs.retries)} />
          </div></section>
          <section className="app-section"><div className="app-grid cols-2">
            <div className="app-card"><h2 className="app-card-title">Status breakdown</h2>
              {Object.keys(data.enquiries.by_status).length ? <Bars values={data.enquiries.by_status} /> : <p className="app-muted">No enquiries recorded.</p>}</div>
            <div className="app-card"><h2 className="app-card-title">Runs by mode</h2>
              {Object.keys(data.runs.by_mode).length ? Object.entries(data.runs.by_mode).map(([mode, statuses]) => <div key={mode} style={{ marginBottom: 10 }}><strong className="app-small">{mode}</strong><Bars values={statuses} /></div>) : <p className="app-muted">No runs recorded.</p>}
              <p className="app-small app-muted">{data.exchanges} recorded exchanges/steps · {data.runs.cancelled} cancelled</p></div>
          </div></section>
          <section className="app-section"><div className="app-grid cols-3">
            <div className="app-card"><h2 className="app-card-title">Review time</h2>
              <dl className="app-kv"><dt>Median</dt><dd>{fmt(data.review_seconds.median, " s")}</dd><dt>p95</dt><dd>{fmt(data.review_seconds.p95, " s")}</dd><dt>Samples</dt><dd>{data.review_seconds.samples}</dd></dl></div>
            <div className="app-card"><h2 className="app-card-title">Model usage</h2>
              {data.tokens ? <dl className="app-kv"><dt>Input tokens</dt><dd>{data.tokens.input}</dd><dt>Output tokens</dt><dd>{data.tokens.output}</dd><dt>Est. cost</dt><dd>${data.tokens.estimated_usd}</dd></dl> : <p className="app-muted">{data.tokens_note}</p>}
              <hr className="app-divider" />
              {data.allowance ? <dl className="app-kv"><dt>Confirmed</dt><dd>${data.allowance.confirmed_usd}</dd><dt>Remaining</dt><dd>${data.allowance.remaining_usd}</dd></dl> : <p className="app-small app-muted">{data.allowance_note}</p>}</div>
            <div className="app-card"><h2 className="app-card-title">Accuracy</h2>
              {data.accuracy ? <><strong style={{ fontSize: 24 }}>{data.accuracy.passed} / {data.accuracy.total}</strong><p className="app-small app-muted">Labelled set <span className="app-mono">{data.accuracy.dataset}</span> (synthetic cases), latest run. Exact match on status and part set.</p></> : <p className="app-muted">{data.accuracy_note}</p>}</div>
          </div></section>
          <section className="app-section"><div className="app-card"><h2 className="app-card-title"><BarChart3 size={16} />Step latency (server-measured)</h2>
            {Object.keys(data.latency_ms).length ? (
              <div className="app-table-wrap"><table className="app-table"><thead><tr><th>Step</th><th>p50</th><th>p95</th><th>Samples</th></tr></thead>
                <tbody>{Object.entries(data.latency_ms).map(([step, v]) => <tr key={step}><td>{step}</td><td>{fmt(v.p50_ms, " ms")}</td><td>{fmt(v.p95_ms, " ms")}</td><td>{v.samples}</td></tr>)}</tbody></table></div>
            ) : <p className="app-muted">No steps recorded yet.</p>}
            <p className="app-small app-muted">Fixture replay pacing (a fixed delay between steps for observability) is not included in these timings.</p>
          </div></section>
        </>
      )}
    </>
  );
}

function Card({ label, value }: { label: string; value: string }): JSX.Element {
  return <div className="app-card app-stat"><strong>{value}</strong><span>{label}</span></div>;
}

function Bars({ values }: { values: Record<string, number> }): JSX.Element {
  const max = Math.max(1, ...Object.values(values));
  return (
    <div className="app-stack" style={{ gap: 6 }}>
      {Object.entries(values).map(([k, v]) => (
        <div key={k} className="app-small"><div className="app-row" style={{ justifyContent: "space-between" }}><span>{k.replace(/_/g, " ")}</span><strong>{v}</strong></div><div className="app-meter"><span style={{ width: `${(v / max) * 100}%` }} /></div></div>
      ))}
    </div>
  );
}
