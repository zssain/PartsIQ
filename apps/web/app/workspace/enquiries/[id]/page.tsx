"use client";

import { Bot, CheckCircle2, CircleDot, Clock, Activity, MessageSquare, PackageCheck, RefreshCw, Repeat, Send, Workflow, XCircle } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type JSX } from "react";

import { useCrumb } from "@/components/app/AppShell";
import { PendingPanel, RunControls } from "@/components/app/RunControls";
import { Alert, ErrorState, Ident, PageHeader, RunStatusBadge, Skeleton, SourceBadge, StatusBadge, useDates, useToast } from "@/components/app/ui";
import { useLabel, useLocale, useT, useTx } from "@/lib/app-i18n";
import { errorMessage, useIdempotentAction, useLoad, useRunEvents } from "@/lib/hooks";
import { useSession } from "@/lib/session";
import { ws, type EnquiryDetail, type ItemDetail, type RunMode } from "@/lib/workspace";

export default function EnquiryDetailPage(): JSX.Element {
  const { id } = useParams<{ id: string }>();
  const { data, error, loading, reload } = useLoad((signal) => ws.detail(id, signal), [id]);
  const { run, events, wake } = useRunEvents(data?.run?.id ?? null);
  const lastSignal = useRef("");
  const t = useT();
  useCrumb(data ? (data.messages[0]?.body ?? t("table.enquiry")).slice(0, 40) : null);

  // Re-read the authoritative detail whenever the run's recorded state moves forward.
  useEffect(() => {
    if (!run) return;
    const signal = `${run.status}:${run.state_version}:${events.length}:${run.revision}`;
    if (signal !== lastSignal.current) {
      lastSignal.current = signal;
      reload();
    }
  }, [run, events.length, reload]);

  const refresh = useCallback(() => { reload(); wake(); }, [reload, wake]);

  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (!data) return loading ? <Skeleton lines={8} /> : <ErrorState error={new Error("Not found")} />;
  const current = run && run.id === data.run?.id ? run : data.run;
  return <Detail d={data} runView={current} refresh={refresh} />;
}

function Detail({ d, runView, refresh }: { d: EnquiryDetail; runView: EnquiryDetail["run"]; refresh: () => void }): JSX.Element {
  const { can } = useSession();
  const router = useRouter();
  const toast = useToast();
  const t = useT();
  const tx = useTx();
  const label = useLabel();
  const locale = useLocale();
  const { time, clock } = useDates();
  const rev = (n: number) => <bdi>{n}</bdi>;
  const title = d.messages[0]?.body ?? t("table.enquiry");
  const [message, setMessage] = useState("");
  const sendMessage = useCallback(async (key: string, text: string) => ws.message(d.id, text, d.revision, key), [d.id, d.revision]);
  const msg = useIdempotentAction(sendMessage);
  const startRun = useCallback(async (key: string, mode: RunMode) => ws.startRun(d.id, mode, d.revision, key), [d.id, d.revision]);
  const start = useIdempotentAction(startRun);
  const repeatFn = useCallback(async (key: string) => ws.repeat(d.id, { locale: d.locale, destination_warehouse_id: d.destination.id }, key), [d.id, d.locale, d.destination.id]);
  const repeat = useIdempotentAction(repeatFn);
  const active = runView && !["awaiting_review", "completed", "cancelled", "failed", "superseded", "needs_staff", "blocked"].includes(runView.status);
  const otherMode: RunMode = d.mode === "guided" ? "collaboration" : "guided";

  return (
    <>
      <PageHeader
        title={title.length > 90 ? `${title.slice(0, 90)}…` : title}
        kicker={<><StatusBadge status={d.status} /><span>{tx("common.revision", { rev: rev(d.revision) })}</span><span>·</span><span>{t(d.mode === "collaboration" ? "mode.collaboration" : "mode.guided")}</span>{runView && <SourceBadge source={runView.execution_source} />}</>}
        description={d.wait_reason ? <span dir="auto">{d.wait_reason}</span> : undefined}
        actions={<>
          {runView && <Link className="app-btn" href={`/workspace/runs/${runView.id}`} data-testid="open-run"><Activity size={15} />{d.mode === "collaboration" ? t("detail.exchanges") : t("detail.activity")}</Link>}
          {d.can_review && <Link className="app-btn" href={`/workspace/review/${d.id}`}>{t("detail.openReview")}</Link>}
        </>}
      />
      {!d.catalogue_current && <Alert tone="warn" title={t("detail.catChanged")}>{t("detail.catChangedBody")}</Alert>}
      {runView?.stale && <Alert tone="warn">{t("detail.stale")}</Alert>}

      <div className="app-split" style={{ marginTop: 16 }}>
        <div className="app-stack">
          {d.pending.map((p) => runView && <PendingPanel key={p.id} pending={p} run={runView} onChanged={refresh} />)}

          {d.published_reply && (
            <section className="app-card" style={{ borderColor: "var(--app-ok)" }} data-testid="approved-reply">
              <h2 className="app-card-title"><CheckCircle2 size={17} color="var(--app-ok)" />{t("detail.approvedTitle")}<span className="app-badge ok">{tx("detail.published", { rev: rev(d.published_reply.revision) })}</span></h2>
              <div className="app-msg recommendation" dir="auto" style={{ maxWidth: "100%" }}>{d.published_reply.body}</div>
              <p className="app-small app-muted" style={{ marginTop: 8 }}>{t("detail.approvedNote", { time: time(d.published_reply.created_at) })}</p>
            </section>
          )}
          {d.status === "rejected" && <Alert tone="warn" title={t("detail.rejectedTitle")}>{t("detail.rejectedBody")}</Alert>}

          <section className="app-card">
            <h2 className="app-card-title"><PackageCheck size={17} />{t("detail.parts")}</h2>
            <div className="app-stack">{d.items.map((item) => <ItemCard key={item.id} item={item} />)}</div>
            {d.nameplate && (
              <div className="app-small" style={{ marginTop: 10 }}>
                {tx("detail.nameplate", { source: label("visionSource", d.nameplate.source), model: <Ident>{d.nameplate.confirmed_model ?? d.nameplate.model_text ?? "—"}</Ident>, serial: <Ident>{d.nameplate.confirmed_serial ?? d.nameplate.serial_text ?? "—"}</Ident> })} · {d.nameplate.confirmed ? <span className="app-badge ok">{t("detail.confirmedByYou")}</span> : <span className="app-badge warn">{t("detail.needsConfirmation")}</span>}
                {d.nameplate.issues.length > 0 && <> · {tx("detail.issues", { list: <bdi>{d.nameplate.issues.join(", ")}</bdi> })}</>}
              </div>
            )}
          </section>

          <section className="app-card">
            <h2 className="app-card-title"><MessageSquare size={17} />{t("detail.conversation")}</h2>
            <div className="app-thread" data-testid="conversation">
              {d.messages.map((m) => (
                <div key={m.id} className={`app-msg ${m.kind}`} dir="auto">
                  <header dir={locale === "ar" ? "rtl" : "ltr"}>{t(m.kind === "customer" ? "detail.msgYou" : m.kind === "recommendation" ? "detail.msgApproved" : m.kind === "clarification" ? "detail.msgQuestion" : "detail.msgUpdate")} · {tx("common.rev", { rev: rev(m.revision) })} · <bdi>{time(m.created_at)}</bdi></header>
                  {m.body}
                </div>
              ))}
              {d.status === "awaiting_review" && <div className="app-msg" style={{ background: "transparent", borderStyle: "dashed" }}>{t("detail.drafted")}</div>}
            </div>
            {d.is_owner && d.status !== "approved" && (
              <form className="app-stack" style={{ marginTop: 12 }} onSubmit={async (e) => {
                e.preventDefault();
                if (!message.trim()) return;
                const ok = await msg.run(message.trim());
                if (ok) { setMessage(""); toast("ok", t("detail.msgAdded")); refresh(); }
              }}>
                <label className="app-field"><span>{t("detail.addDetails")}</span><textarea className="app-textarea" style={{ minHeight: 70 }} value={message} onChange={(e) => setMessage(e.target.value)} dir="auto" maxLength={12000} placeholder={t("detail.followupPlaceholder")} data-testid="followup-text" /></label>
                {msg.error && <Alert tone="danger"><span dir="auto">{errorMessage(msg.error)}</span> {t("detail.keptText")}</Alert>}
                <div><button className="app-btn small" disabled={msg.pending || !message.trim()} type="submit"><Send size={14} />{t("common.send")}</button></div>
              </form>
            )}
          </section>
        </div>

        <aside className="app-stack">
          <section className="app-card" data-testid="customer-progress">
            <h2 className="app-card-title"><Clock size={16} />{t("detail.progress")}<span className="app-small app-muted">{tx("common.rev", { rev: rev(d.revision) })}</span></h2>
            <ol className="app-steps">
              {d.events.length === 0 && <li data-state="active"><span className="app-step-icon"><CircleDot size={12} /></span><div><strong>{d.status === "received" ? t("detail.waitingStart") : t("detail.starting")}</strong><p dir="auto">{d.wait_reason ?? t("detail.stepsAppear")}</p></div></li>}
              {d.events.map((e, i) => (
                <li key={`${e.step}-${i}`} data-state={e.status} data-step={e.step}>
                  <span className="app-step-icon">{e.status === "done" ? <CheckCircle2 size={12} /> : e.status === "failed" ? <XCircle size={12} /> : <Clock size={12} />}</span>
                  <div><strong>{label("step", e.step, e.label)}</strong>{e.detail && <p dir="auto">{e.detail}</p>}<p className="app-small">{clock(e.at)}</p></div>
                </li>
              ))}
            </ol>
          </section>
          {runView && d.can_control && (
            <section className="app-card">
              <h2 className="app-card-title">{runView.mode === "collaboration" ? <Bot size={16} /> : <Workflow size={16} />}{t("detail.runControl")}</h2>
              <RunControls run={runView} onChanged={refresh} compact />
              <Link className="app-btn small" style={{ marginTop: 10 }} href={`/workspace/runs/${runView.id}`}>{t("detail.openRun")}</Link>
            </section>
          )}
          {d.can_control && !active && d.status !== "approved" && can("enquiry.create") && (
            <section className="app-card sunken app-stack">
              <h2 className="app-card-title"><Repeat size={16} />{t("detail.runAgain")}</h2>
              <p className="app-small app-muted">{t("detail.runAgainBody")}</p>
              <div className="app-row">
                <button className="app-btn small" disabled={start.pending} onClick={async () => { const r = await start.run(d.mode); if (r) { toast("ok", t("detail.runStarted")); refresh(); } }}><RefreshCw size={14} />{t(d.mode === "collaboration" ? "detail.newRun.collaboration" : "detail.newRun.guided")}</button>
                <button className="app-btn small" disabled={start.pending} onClick={async () => { const r = await start.run(otherMode); if (r) { toast("ok", t(otherMode === "collaboration" ? "detail.otherStarted.collaboration" : "detail.otherStarted.guided")); router.push(`/workspace/runs/${r.id}`); } }} data-testid="start-other-mode">{otherMode === "collaboration" ? <Bot size={14} /> : <Workflow size={14} />}{t(otherMode === "collaboration" ? "detail.try.collaboration" : "detail.try.guided")}</button>
              </div>
              {start.error && <Alert tone="danger">{errorMessage(start.error)}</Alert>}
            </section>
          )}
          {d.status === "approved" && d.is_owner && can("enquiry.create") && (
            <section className="app-card sunken app-stack">
              <h2 className="app-card-title"><Repeat size={16} />{t("detail.orderAgain")}</h2>
              <p className="app-small app-muted">{t("detail.orderAgainBody")}</p>
              <div><button className="app-btn small" disabled={repeat.pending} data-testid="repeat-enquiry" onClick={async () => { const r = await repeat.run(); if (r) { toast("ok", t("detail.repeated")); router.push(`/workspace/enquiries/${r.id}`); } }}><Repeat size={14} />{t("detail.repeat")}</button></div>
              {repeat.error && <Alert tone="danger">{errorMessage(repeat.error)}</Alert>}
            </section>
          )}
          {d.runs.length > 1 && (
            <section className="app-card">
              <h2 className="app-card-title">{t("detail.runHistory")}</h2>
              <div className="app-list app-small">
                {d.runs.map((r) => (
                  <Link key={r.id} href={`/workspace/runs/${r.id}`} className="app-row" style={{ textDecoration: "none", justifyContent: "space-between" }}>
                    <span>{label("modeShort", r.mode)} · {tx("common.rev", { rev: rev(r.revision) })}</span><RunStatusBadge status={r.status} />
                  </Link>
                ))}
              </div>
            </section>
          )}
          <section className="app-card sunken">
            <dl className="app-kv app-small">
              <dt>{t("detail.destination")}</dt><dd>{d.destination.name}</dd>
              <dt>{t("common.created")}</dt><dd>{time(d.created_at)}</dd>
              <dt>{t("common.updated")}</dt><dd>{time(d.updated_at)}</dd>
              <dt>{t("detail.reference")}</dt><dd><Ident>{d.id.slice(0, 8)}</Ident></dd>
            </dl>
          </section>
        </aside>
      </div>
    </>
  );
}

function ItemCard({ item }: { item: ItemDetail }): JSX.Element {
  const t = useT();
  const tx = useTx();
  const statusKey = item.status === "ready" ? "itemStatus.ready" : item.status === "needs_information" ? "itemStatus.needs_information" : item.status === "unavailable" ? "itemStatus.unavailable" : "itemStatus.checking";
  return (
    <div className="app-evidence" data-testid="item-card" data-item-status={item.status}>
      <header>
        <strong dir="auto">{item.quantity ?? "?"} × {item.description}</strong>
        <span className={`app-badge ${item.status === "ready" ? "ok" : item.status === "needs_information" ? "warn" : item.status === "unavailable" ? "danger" : "info"}`}>{t(statusKey)}</span>
        {item.quantity_assumed && <span className="app-badge warn" title={t("detail.qtyAssumedTitle")}>{t("detail.qtyAssumed")}</span>}
      </header>
      <div className="app-small app-muted">
        {tx("detail.machine", { machine: item.configuration_label ? <bdi>{item.configuration_label}</bdi> : item.model_text ? <Ident>{item.model_text}</Ident> : t("detail.notIdentified") })}{item.serial_text && tx("detail.serial", { serial: <Ident>{item.serial_text}</Ident> })}
      </div>
      {item.identification_note && <div className="app-small app-muted" dir="auto">{item.identification_note}</div>}
      {item.quoted_number_note && <div className="app-small" dir="auto">{item.quoted_number_note}</div>}
      {item.selected && (
        <div className="app-small">
          {tx("detail.compatiblePart", { part: <Ident>{item.selected.part_number}</Ident>, name: <><bdi>{item.selected.name_en}</bdi> <bdi dir="rtl">({item.selected.name_ar})</bdi></> })}
          <div className="app-muted">{tx("detail.fitmentSource", { ref: <Ident>{item.selected.source_reference}</Ident> })}{item.selected.superseded_from.length > 0 && tx("detail.replaces", { parts: <Ident>{item.selected.superseded_from.join(", ")}</Ident> })}</div>
        </div>
      )}
      {item.plan && (
        <div className="app-small">
          <span dir="auto">{item.plan.message}</span>
          {item.plan.shortage > 0 && <span className="app-badge warn" style={{ marginInlineStart: 6 }}>{t("detail.shortBy", { n: item.plan.shortage })}</span>}
          <div className="app-muted">{t("detail.transferNote")}</div>
        </div>
      )}
    </div>
  );
}
