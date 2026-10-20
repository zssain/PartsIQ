"use client";

import { RotateCcw } from "lucide-react";
import Link from "next/link";
import { useState, type JSX } from "react";

import { Alert, EmptyState, ErrorState, Ident, PageHeader, PermissionDenied, Skeleton, useDates, useToast } from "@/components/app/ui";
import { useLabel, useT } from "@/lib/app-i18n";
import { errorMessage, useLoad } from "@/lib/hooks";
import { useSession } from "@/lib/session";
import { ws } from "@/lib/workspace";

export default function JobsPage(): JSX.Element {
  const { can } = useSession();
  const toast = useToast();
  const t = useT();
  const label = useLabel();
  const { time } = useDates();
  const [status, setStatus] = useState("");
  const { data, error, loading, reload } = useLoad(() => ws.jobs(status || undefined), [status]);
  const [err, setErr] = useState<unknown>(null);
  if (!can("jobs.read")) return <PermissionDenied />;
  return (
    <>
      <PageHeader title={t("nav.jobs")} description={t("jobs.desc")} />
      {data && (
        <section className="app-card" style={{ marginBottom: 16 }}>
          <h2 className="app-card-title">{t("jobs.dependencies")}</h2>
          <div className="app-table-wrap"><table className="app-table"><tbody>{data.dependencies.map((d) => <tr key={d.name}><td><strong><bdi>{d.name}</bdi></strong></td><td><span className={`app-badge ${d.state === "available" || d.state === "configured" ? "ok" : d.state === "unavailable" ? "danger" : "outline"}`}>{label("depState", d.state.replace(/\s+/g, "_"), d.state)}</span></td><td className="app-small app-muted" dir="auto">{d.detail}</td></tr>)}</tbody></table></div>
        </section>
      )}
      <div className="app-seg" role="group" aria-label={t("jobs.statusAria")} style={{ marginBottom: 12 }}>
        {["", "pending", "running", "succeeded", "failed", "cancelled"].map((s) => <button key={s || "all"} aria-pressed={status === s} onClick={() => setStatus(s)}>{s ? label("jobStatus", s) : t("common.all")}{data?.counts[s] ? ` (${data.counts[s]})` : ""}</button>)}
      </div>
      {err !== null && <Alert tone="danger">{errorMessage(err)}</Alert>}
      {error ? <ErrorState error={error} onRetry={reload} /> : loading && !data ? <Skeleton lines={5} /> : data && (data.items.length ? (
        <div className="app-table-wrap"><table className="app-table" data-testid="jobs-table">
          <thead><tr><th>{t("jobs.thJob")}</th><th>{t("common.status")}</th><th>{t("jobs.thAttempts")}</th><th>{t("jobs.thError")}</th><th>{t("common.updated")}</th><th /></tr></thead>
          <tbody>{data.items.map((j) => (
            <tr key={j.id}>
              <td><Ident>{j.kind}</Ident><div className="app-small app-muted">{j.kind.startsWith("workflow") ? <Link href={`/workspace/runs/${j.id}`}><Ident>{j.id.slice(0, 8)}</Ident></Link> : <Ident>{j.id.slice(0, 8)}</Ident>} · {label("execSource", j.execution_source)}</div></td>
              <td><span className={`app-badge ${j.status === "succeeded" ? "ok" : j.status === "failed" ? "danger" : j.status === "running" ? "info" : "outline"}`}>{label("jobStatus", j.status)}</span></td>
              <td>{j.attempts}</td>
              <td className="app-small">{j.error_code ? <><bdi>{j.error_category}</bdi>: <Ident>{j.error_code}</Ident></> : "—"}</td>
              <td className="app-small app-muted">{time(j.updated_at)}</td>
              <td>{j.retryable && can("jobs.retry") && j.revision && <button className="app-btn small" onClick={async () => { try { await ws.retryJob(j.id, j.revision!, crypto.randomUUID()); toast("ok", t("jobs.retryToast")); reload(); } catch (e) { setErr(e); } }}><RotateCcw size={13} />{t("jobs.retry")}</button>}</td>
            </tr>
          ))}</tbody>
        </table></div>
      ) : <EmptyState title={t("jobs.empty")} body={t("jobs.emptyBody")} />)}
    </>
  );
}
