"use client";

import { RotateCcw } from "lucide-react";
import Link from "next/link";
import { useState, type JSX } from "react";

import { Alert, EmptyState, ErrorState, PageHeader, PermissionDenied, Skeleton, formatTime, useToast } from "@/components/app/ui";
import { errorMessage, useLoad } from "@/lib/hooks";
import { useSession } from "@/lib/session";
import { ws } from "@/lib/workspace";

export default function JobsPage(): JSX.Element {
  const { can } = useSession();
  const toast = useToast();
  const [status, setStatus] = useState("");
  const { data, error, loading, reload } = useLoad(() => ws.jobs(status || undefined), [status]);
  const [err, setErr] = useState<unknown>(null);
  if (!can("jobs.read")) return <PermissionDenied />;
  return (
    <>
      <PageHeader title="Jobs & operations" description="Runs and background jobs with their status, attempts and error category. Errors are categorised; internal details and secrets are never shown." />
      {data && (
        <section className="app-card" style={{ marginBottom: 16 }}>
          <h2 className="app-card-title">Dependencies</h2>
          <div className="app-table-wrap"><table className="app-table"><tbody>{data.dependencies.map((d) => <tr key={d.name}><td><strong>{d.name}</strong></td><td><span className={`app-badge ${d.state === "available" || d.state === "configured" ? "ok" : d.state === "unavailable" ? "danger" : "outline"}`}>{d.state}</span></td><td className="app-small app-muted">{d.detail}</td></tr>)}</tbody></table></div>
        </section>
      )}
      <div className="app-seg" role="group" aria-label="Job status" style={{ marginBottom: 12 }}>
        {["", "pending", "running", "succeeded", "failed", "cancelled"].map((s) => <button key={s || "all"} aria-pressed={status === s} onClick={() => setStatus(s)}>{s || "All"}{data?.counts[s] ? ` (${data.counts[s]})` : ""}</button>)}
      </div>
      {err !== null && <Alert tone="danger">{errorMessage(err)}</Alert>}
      {error ? <ErrorState error={error} onRetry={reload} /> : loading && !data ? <Skeleton lines={5} /> : data && (data.items.length ? (
        <div className="app-table-wrap"><table className="app-table" data-testid="jobs-table">
          <thead><tr><th>Job</th><th>Status</th><th>Attempts</th><th>Error</th><th>Updated</th><th /></tr></thead>
          <tbody>{data.items.map((j) => (
            <tr key={j.id}>
              <td><span className="app-mono">{j.kind}</span><div className="app-small app-muted">{j.kind.startsWith("workflow") ? <Link href={`/workspace/runs/${j.id}`}>{j.id.slice(0, 8)}</Link> : j.id.slice(0, 8)} · {j.execution_source}</div></td>
              <td><span className={`app-badge ${j.status === "succeeded" ? "ok" : j.status === "failed" ? "danger" : j.status === "running" ? "info" : "outline"}`}>{j.status}</span></td>
              <td>{j.attempts}</td>
              <td className="app-small">{j.error_code ? <>{j.error_category}: <span className="app-mono">{j.error_code}</span></> : "—"}</td>
              <td className="app-small app-muted">{formatTime(j.updated_at)}</td>
              <td>{j.retryable && can("jobs.retry") && j.revision && <button className="app-btn small" onClick={async () => { try { await ws.retryJob(j.id, j.revision!, crypto.randomUUID()); toast("ok", "Retry started as a new run."); reload(); } catch (e) { setErr(e); } }}><RotateCcw size={13} />Retry</button>}</td>
            </tr>
          ))}</tbody>
        </table></div>
      ) : <EmptyState title="No jobs" body="Runs and imports appear here." />)}
    </>
  );
}
