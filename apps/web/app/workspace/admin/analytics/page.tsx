"use client";

import { BarChart3 } from "lucide-react";
import type { JSX } from "react";

import { Alert, ErrorState, PageHeader, PermissionDenied, Skeleton } from "@/components/app/ui";
import { useLabel, useT, useTx, type TKey } from "@/lib/app-i18n";
import { useLoad } from "@/lib/hooks";
import { useSession } from "@/lib/session";
import { ws } from "@/lib/workspace";

export default function AnalyticsPage(): JSX.Element {
  const { can } = useSession();
  const t = useT();
  const tx = useTx();
  const label = useLabel();
  // Missing measurements say so (never a zero); units follow the UI language.
  const fmt = (v: number | null | undefined, unit?: TKey) => {
    if (v === null || v === undefined) return t("common.notMeasured");
    const n = Math.round(v * 10) / 10;
    return unit ? t(unit, { v: n }) : String(n);
  };
  const { data, error, loading, reload } = useLoad(() => ws.analytics());
  if (!can("analytics.read")) return <PermissionDenied />;
  return (
    <>
      <PageHeader title={t("nav.analytics")} description={t("an.desc")} />
      {error ? <ErrorState error={error} onRetry={reload} /> : loading && !data ? <Skeleton lines={6} /> : data && (
        <>
          <Alert tone="info" title={data.scope === "demo" ? t("an.scopeDemo") : t("an.scopeAccount")}><span dir="auto">{data.scope_note}</span></Alert>
          <section className="app-section"><div className="app-grid cols-4" data-testid="analytics-stats">
            <Card label={t("an.enquiries")} value={String(data.enquiries.total)} />
            <Card label={t("an.runs")} value={String(data.runs.total)} />
            <Card label={t("an.failedRuns")} value={String(data.runs.failed)} />
            <Card label={t("an.retries")} value={String(data.runs.retries)} />
          </div></section>
          <section className="app-section"><div className="app-grid cols-2">
            <div className="app-card"><h2 className="app-card-title">{t("an.statusBreakdown")}</h2>
              {Object.keys(data.enquiries.by_status).length ? <Bars values={data.enquiries.by_status} prefix="status" /> : <p className="app-muted">{t("an.noEnquiries")}</p>}</div>
            <div className="app-card"><h2 className="app-card-title">{t("an.runsByMode")}</h2>
              {Object.keys(data.runs.by_mode).length ? Object.entries(data.runs.by_mode).map(([mode, statuses]) => <div key={mode} style={{ marginBottom: 10 }}><strong className="app-small">{label("mode", mode)}</strong><Bars values={statuses} prefix="runStatus" /></div>) : <p className="app-muted">{t("an.noRuns")}</p>}
              <p className="app-small app-muted">{t("an.exchanges", { n: data.exchanges, c: data.runs.cancelled })}</p></div>
          </div></section>
          <section className="app-section"><div className="app-grid cols-3">
            <div className="app-card"><h2 className="app-card-title">{t("an.reviewTime")}</h2>
              <dl className="app-kv"><dt>{t("an.median")}</dt><dd>{fmt(data.review_seconds.median, "an.unitS")}</dd><dt>p95</dt><dd>{fmt(data.review_seconds.p95, "an.unitS")}</dd><dt>{t("an.samples")}</dt><dd>{data.review_seconds.samples}</dd></dl></div>
            <div className="app-card"><h2 className="app-card-title">{t("an.modelUsage")}</h2>
              {data.tokens ? <dl className="app-kv"><dt>{t("an.inputTokens")}</dt><dd>{data.tokens.input}</dd><dt>{t("an.outputTokens")}</dt><dd>{data.tokens.output}</dd><dt>{t("an.estCost")}</dt><dd><bdi>${data.tokens.estimated_usd}</bdi></dd></dl> : <p className="app-muted" dir="auto">{data.tokens_note}</p>}
              <hr className="app-divider" />
              {data.allowance ? <dl className="app-kv"><dt>{t("an.confirmed")}</dt><dd><bdi>${data.allowance.confirmed_usd}</bdi></dd><dt>{t("an.remaining")}</dt><dd><bdi>${data.allowance.remaining_usd}</bdi></dd></dl> : <p className="app-small app-muted" dir="auto">{data.allowance_note}</p>}</div>
            <div className="app-card"><h2 className="app-card-title">{t("an.accuracy")}</h2>
              {data.accuracy ? <><strong style={{ fontSize: 24 }}>{data.accuracy.passed} / {data.accuracy.total}</strong><p className="app-small app-muted">{tx("an.accuracyNote", { dataset: <bdi className="app-mono">{data.accuracy.dataset}</bdi> })}</p></> : <p className="app-muted" dir="auto">{data.accuracy_note}</p>}</div>
          </div></section>
          <section className="app-section"><div className="app-card"><h2 className="app-card-title"><BarChart3 size={16} />{t("an.latency")}</h2>
            {Object.keys(data.latency_ms).length ? (
              <div className="app-table-wrap"><table className="app-table"><thead><tr><th>{t("an.step")}</th><th>p50</th><th>p95</th><th>{t("an.samples")}</th></tr></thead>
                <tbody>{Object.entries(data.latency_ms).map(([step, v]) => <tr key={step}><td>{label("step", step) !== step ? label("step", step) : label("participant", step)}</td><td>{fmt(v.p50_ms, "an.unitMs")}</td><td>{fmt(v.p95_ms, "an.unitMs")}</td><td>{v.samples}</td></tr>)}</tbody></table></div>
            ) : <p className="app-muted">{t("an.noSteps")}</p>}
            <p className="app-small app-muted">{t("an.pacingNote")}</p>
          </div></section>
        </>
      )}
    </>
  );
}

function Card({ label, value }: { label: string; value: string }): JSX.Element {
  return <div className="app-card app-stat"><strong>{value}</strong><span>{label}</span></div>;
}

function Bars({ values, prefix }: { values: Record<string, number>; prefix: "status" | "runStatus" }): JSX.Element {
  const label = useLabel();
  const max = Math.max(1, ...Object.values(values));
  return (
    <div className="app-stack" style={{ gap: 6 }}>
      {Object.entries(values).map(([k, v]) => (
        <div key={k} className="app-small"><div className="app-row" style={{ justifyContent: "space-between" }}><span>{label(prefix, k, k.replace(/_/g, " "))}</span><strong>{v}</strong></div><div className="app-meter"><span style={{ width: `${(v / max) * 100}%` }} /></div></div>
      ))}
    </div>
  );
}
