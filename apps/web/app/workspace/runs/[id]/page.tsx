"use client";

import { ArrowLeft, Bot, Users, Workflow, WifiOff } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type JSX } from "react";

import { useCrumb } from "@/components/app/AppShell";
import { ExchangeFeed } from "@/components/app/ExchangeFeed";
import { PendingPanel, RunControls } from "@/components/app/RunControls";
import { Alert, ErrorState, PageHeader, RunStatusBadge, Skeleton, SourceBadge, formatTime } from "@/components/app/ui";
import { useRunEvents } from "@/lib/hooks";

export default function RunPage(): JSX.Element {
  const { id } = useParams<{ id: string }>();
  const { events, run, error, stopped, wake } = useRunEvents(id);
  const [firstSeq, setFirstSeq] = useState(0);
  const seeded = useRef(false);
  useCrumb(run ? `${run.mode === "collaboration" ? "Collaboration" : "Guided"} run · rev ${run.revision}` : null);
  useEffect(() => {
    // Mark only events that arrive after the first load as "new" (no animation for history).
    if (!seeded.current && events.length) {
      seeded.current = true;
      setFirstSeq(events[events.length - 1].seq);
    }
  }, [events]);
  const changed = useCallback(() => wake(), [wake]);

  if (error && !run) return <ErrorState error={error} onRetry={wake} />;
  if (!run) return <Skeleton lines={8} />;
  const collab = run.mode === "collaboration";
  return (
    <>
      <PageHeader
        title={collab ? "Agent collaboration" : "Guided workflow run"}
        kicker={<><RunStatusBadge status={run.status} /><SourceBadge source={run.execution_source} /><span>Enquiry revision {run.revision}{run.stale ? ` (current: ${run.current_revision})` : ""}</span></>}
        description={collab
          ? "Addressed messages between specialists and the deterministic services they called, as recorded by the controller. Specialists only propose; code decides compatibility, verification and what may run next."
          : "Each step the deterministic workflow executed, with its recorded outcome. Routing between steps is fixed code; no model chooses the next step."}
        actions={<Link className="app-btn" href={`/workspace/enquiries/${run.enquiry_id}`}><ArrowLeft size={15} />Enquiry</Link>}
      />
      {run.stale && <Alert tone="warn" title="Stale run">A newer revision of the enquiry exists. This run is kept for the audit trail but can no longer produce a draft.</Alert>}
      {error && <Alert tone="warn"><WifiOff size={14} /> Connection interrupted — retrying with backoff. Events already shown are kept and will not be duplicated.</Alert>}
      <div className="app-collab" style={{ marginTop: 12 }}>
        <section aria-label="Run events">
          <ExchangeFeed events={events} freshFrom={firstSeq} />
          {stopped && <p className="app-small app-muted" style={{ marginTop: 10 }}>Live updates paused: the run is waiting or finished. Actions you take here resume them.</p>}
        </section>
        <aside className="app-stack">
          {run.pending.map((p) => <PendingPanel key={p.id} pending={p} run={run} onChanged={changed} />)}
          <section className="app-card">
            <h2 className="app-card-title">{collab ? <Bot size={16} /> : <Workflow size={16} />}Run control</h2>
            <RunControls run={run} onChanged={changed} />
          </section>
          <section className="app-card" data-testid="roster">
            <h2 className="app-card-title"><Users size={16} />{collab ? "Specialists & services" : "Workflow & services"}</h2>
            <div className="app-roster">
              {run.roster.map((r) => (
                <div key={r.id} data-state={r.state} data-participant={r.id}>
                  <span className="app-dot" aria-hidden="true" />
                  <span style={{ flex: 1 }}>{r.label}<span className="app-small app-muted"> · {r.type === "agent" ? "AI specialist" : r.type === "service" ? "deterministic service" : "workflow"}</span></span>
                  <span className="app-small app-muted">{r.state}{r.messages ? ` · ${r.messages}` : ""}</span>
                </div>
              ))}
            </div>
            {collab && <p className="app-small app-muted" style={{ marginTop: 8 }}>Only the four specialists are AI roles. Identification, compatibility search, fulfilment and verification are deterministic code.</p>}
          </section>
          <section className="app-card sunken">
            <dl className="app-kv app-small">
              <dt>Started</dt><dd>{formatTime(run.created_at)}</dd>
              <dt>Updated</dt><dd>{formatTime(run.updated_at)}</dd>
              {run.completed_at && <><dt>Finished</dt><dd>{formatTime(run.completed_at)}</dd></>}
              <dt>Catalogue</dt><dd className="app-mono">{run.catalogue_version_id.slice(0, 8)}</dd>
              {run.carried_from && <><dt>Continues</dt><dd><Link href={`/workspace/runs/${run.carried_from}`}>earlier run</Link></dd></>}
            </dl>
          </section>
        </aside>
      </div>
    </>
  );
}
