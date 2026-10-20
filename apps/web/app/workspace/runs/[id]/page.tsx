"use client";

import { ArrowLeft, Bot, Users, Workflow, WifiOff } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useState, type JSX } from "react";

import { useCrumb } from "@/components/app/AppShell";
import { ExchangeFeed } from "@/components/app/ExchangeFeed";
import { PendingPanel, RunControls } from "@/components/app/RunControls";
import { Alert, ErrorState, Ident, PageHeader, RunStatusBadge, Skeleton, SourceBadge, useDates } from "@/components/app/ui";
import { useLabel, useT, useTx } from "@/lib/app-i18n";
import { useRunEvents } from "@/lib/hooks";

export default function RunPage(): JSX.Element {
  const { id } = useParams<{ id: string }>();
  const { events, run, error, stopped, wake } = useRunEvents(id);
  const [firstSeq, setFirstSeq] = useState(0);
  const [seededFirst, setSeededFirst] = useState(false);
  const t = useT();
  const tx = useTx();
  const label = useLabel();
  const { time } = useDates();
  useCrumb(run ? t(run.mode === "collaboration" ? "run.crumb.collaboration" : "run.crumb.guided", { rev: run.revision }) : null);
  // Mark only events that arrive after the first load as "new" (no animation for history).
  // Set while rendering, once, when the first page arrives.
  if (!seededFirst && events.length) {
    setSeededFirst(true);
    setFirstSeq(events[events.length - 1].seq);
  }
  const changed = useCallback(() => wake(), [wake]);

  if (error && !run) return <ErrorState error={error} onRetry={wake} />;
  if (!run) return <Skeleton lines={8} />;
  const collab = run.mode === "collaboration";
  return (
    <>
      <PageHeader
        title={collab ? t("mode.collaboration") : t("run.titleGuided")}
        kicker={<><RunStatusBadge status={run.status} /><SourceBadge source={run.execution_source} /><span>{tx("run.enquiryRev", { rev: <bdi>{run.revision}</bdi> })}{run.stale ? tx("run.currentRev", { rev: <bdi>{run.current_revision}</bdi> }) : ""}</span></>}
        description={collab ? t("run.descCollab") : t("run.descGuided")}
        actions={<Link className="app-btn" href={`/workspace/enquiries/${run.enquiry_id}`}><ArrowLeft size={15} className="app-flip-rtl" />{t("run.backEnquiry")}</Link>}
      />
      {run.stale && <Alert tone="warn" title={t("run.staleTitle")}>{t("run.staleBody")}</Alert>}
      {error && <Alert tone="warn"><WifiOff size={14} /> {t("run.connection")}</Alert>}
      <div className="app-collab" style={{ marginTop: 12 }}>
        <section aria-label={t("run.eventsAria")}>
          <ExchangeFeed events={events} freshFrom={firstSeq} />
          {stopped && <p className="app-small app-muted" style={{ marginTop: 10 }}>{t("run.livePaused")}</p>}
        </section>
        <aside className="app-stack">
          {run.pending.map((p) => <PendingPanel key={p.id} pending={p} run={run} onChanged={changed} />)}
          <section className="app-card">
            <h2 className="app-card-title">{collab ? <Bot size={16} /> : <Workflow size={16} />}{t("detail.runControl")}</h2>
            <RunControls run={run} onChanged={changed} />
          </section>
          <section className="app-card" data-testid="roster">
            <h2 className="app-card-title"><Users size={16} />{collab ? t("run.rosterCollab") : t("run.rosterGuided")}</h2>
            <div className="app-roster">
              {run.roster.map((r) => (
                <div key={r.id} data-state={r.state} data-participant={r.id}>
                  <span className="app-dot" aria-hidden="true" />
                  <span style={{ flex: 1 }}>{label("participant", r.id, r.label)}<span className="app-small app-muted"> · {label("participantType", r.type)}</span></span>
                  <span className="app-small app-muted">{label("rosterState", r.state)}{r.messages ? ` · ${r.messages}` : ""}</span>
                </div>
              ))}
            </div>
            {collab && <p className="app-small app-muted" style={{ marginTop: 8 }}>{t("run.collabNote")}</p>}
          </section>
          <section className="app-card sunken">
            <dl className="app-kv app-small">
              <dt>{t("run.started")}</dt><dd>{time(run.created_at)}</dd>
              <dt>{t("common.updated")}</dt><dd>{time(run.updated_at)}</dd>
              {run.completed_at && <><dt>{t("run.finished")}</dt><dd>{time(run.completed_at)}</dd></>}
              <dt>{t("run.catalogue")}</dt><dd><Ident>{run.catalogue_version_id.slice(0, 8)}</Ident></dd>
              {run.carried_from && <><dt>{t("run.continues")}</dt><dd><Link href={`/workspace/runs/${run.carried_from}`}>{t("run.earlierRun")}</Link></dd></>}
            </dl>
          </section>
        </aside>
      </div>
    </>
  );
}
