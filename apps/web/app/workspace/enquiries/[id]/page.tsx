"use client";

import { Bot, CheckCircle2, CircleDot, Clock, Activity, MessageSquare, PackageCheck, RefreshCw, Repeat, Send, Workflow, XCircle } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type JSX } from "react";

import { useCrumb } from "@/components/app/AppShell";
import { PendingPanel, RunControls } from "@/components/app/RunControls";
import { Alert, ErrorState, Ident, PageHeader, RunStatusBadge, Skeleton, SourceBadge, StatusBadge, formatTime, useToast } from "@/components/app/ui";
import { errorMessage, useIdempotentAction, useLoad, useRunEvents } from "@/lib/hooks";
import { useSession } from "@/lib/session";
import { ws, type EnquiryDetail, type ItemDetail, type RunMode } from "@/lib/workspace";

export default function EnquiryDetailPage(): JSX.Element {
  const { id } = useParams<{ id: string }>();
  const { data, error, loading, reload } = useLoad((signal) => ws.detail(id, signal), [id]);
  const { run, events, wake } = useRunEvents(data?.run?.id ?? null);
  const lastSignal = useRef("");
  useCrumb(data ? (data.messages[0]?.body ?? "Enquiry").slice(0, 40) : null);

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
  const title = d.messages[0]?.body ?? "Enquiry";
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
        kicker={<><StatusBadge status={d.status} /><span>Revision {d.revision}</span><span>·</span><span>{d.mode === "collaboration" ? "Agent collaboration" : "Guided workflow"}</span>{runView && <SourceBadge source={runView.execution_source} />}</>}
        description={d.wait_reason ?? undefined}
        actions={<>
          {runView && <Link className="app-btn" href={`/workspace/runs/${runView.id}`} data-testid="open-run"><Activity size={15} />{d.mode === "collaboration" ? "Specialist exchanges" : "Run activity"}</Link>}
          {d.can_review && <Link className="app-btn" href={`/workspace/review/${d.id}`}>Open review</Link>}
        </>}
      />
      {!d.catalogue_current && <Alert tone="warn" title="Catalogue changed">This enquiry was processed against an earlier catalogue version. Start a new run to re-check it against the current one.</Alert>}
      {runView?.stale && <Alert tone="warn">The run shown is stale — a newer revision exists.</Alert>}

      <div className="app-split" style={{ marginTop: 16 }}>
        <div className="app-stack">
          {d.pending.map((p) => runView && <PendingPanel key={p.id} pending={p} run={runView} onChanged={refresh} />)}

          {d.published_reply && (
            <section className="app-card" style={{ borderColor: "var(--app-ok)" }} data-testid="approved-reply">
              <h2 className="app-card-title"><CheckCircle2 size={17} color="var(--app-ok)" />Approved recommendation<span className="app-badge ok">Published · revision {d.published_reply.revision}</span></h2>
              <div className="app-msg recommendation" dir="auto" style={{ maxWidth: "100%" }}>{d.published_reply.body}</div>
              <p className="app-small app-muted" style={{ marginTop: 8 }}>Reviewed and approved by a person on {formatTime(d.published_reply.created_at)}. Transfer times are estimates, not guarantees. Nothing has been reserved or ordered.</p>
            </section>
          )}
          {d.status === "rejected" && <Alert tone="warn" title="Returned by a reviewer">A reviewer did not approve the draft. Our staff will follow up; no recommendation was published.</Alert>}

          <section className="app-card">
            <h2 className="app-card-title"><PackageCheck size={17} />Requested parts</h2>
            <div className="app-stack">{d.items.map((item) => <ItemCard key={item.id} item={item} />)}</div>
            {d.nameplate && (
              <div className="app-small" style={{ marginTop: 10 }}>
                Nameplate ({d.nameplate.source} vision): model <Ident>{d.nameplate.confirmed_model ?? d.nameplate.model_text ?? "—"}</Ident>, serial <Ident>{d.nameplate.confirmed_serial ?? d.nameplate.serial_text ?? "—"}</Ident> · {d.nameplate.confirmed ? <span className="app-badge ok">Confirmed by you</span> : <span className="app-badge warn">Needs confirmation</span>}
                {d.nameplate.issues.length > 0 && <> · issues: {d.nameplate.issues.join(", ")}</>}
              </div>
            )}
          </section>

          <section className="app-card">
            <h2 className="app-card-title"><MessageSquare size={17} />Conversation</h2>
            <div className="app-thread" data-testid="conversation">
              {d.messages.map((m) => (
                <div key={m.id} className={`app-msg ${m.kind}`} dir="auto">
                  <header>{m.kind === "customer" ? "You" : m.kind === "recommendation" ? "PartsIQ (approved)" : m.kind === "clarification" ? "Question" : "Update"} · rev {m.revision} · {formatTime(m.created_at)}</header>
                  {m.body}
                </div>
              ))}
              {d.status === "awaiting_review" && <div className="app-msg" style={{ background: "transparent", borderStyle: "dashed" }}>A reply has been drafted and is waiting for a staff reviewer. Drafts are never shown to you before approval.</div>}
            </div>
            {d.is_owner && d.status !== "approved" && (
              <form className="app-stack" style={{ marginTop: 12 }} onSubmit={async (e) => {
                e.preventDefault();
                if (!message.trim()) return;
                const ok = await msg.run(message.trim());
                if (ok) { setMessage(""); toast("ok", "Message added — the enquiry is re-checked as a new revision."); refresh(); }
              }}>
                <label className="app-field"><span>Add details</span><textarea className="app-textarea" style={{ minHeight: 70 }} value={message} onChange={(e) => setMessage(e.target.value)} dir="auto" maxLength={12000} placeholder="Correct the model, serial or quantity, or add another part." data-testid="followup-text" /></label>
                {msg.error && <Alert tone="danger">{errorMessage(msg.error)} Your text is kept.</Alert>}
                <div><button className="app-btn small" disabled={msg.pending || !message.trim()} type="submit"><Send size={14} />Send</button></div>
              </form>
            )}
          </section>
        </div>

        <aside className="app-stack">
          <section className="app-card" data-testid="customer-progress">
            <h2 className="app-card-title"><Clock size={16} />Progress<span className="app-small app-muted">rev {d.revision}</span></h2>
            <ol className="app-steps">
              {d.events.length === 0 && <li data-state="active"><span className="app-step-icon"><CircleDot size={12} /></span><div><strong>{d.status === "received" ? "Waiting to start" : "Starting"}</strong><p>{d.wait_reason ?? "Recorded steps appear as they run."}</p></div></li>}
              {d.events.map((e, i) => (
                <li key={`${e.step}-${i}`} data-state={e.status} data-step={e.step}>
                  <span className="app-step-icon">{e.status === "done" ? <CheckCircle2 size={12} /> : e.status === "failed" ? <XCircle size={12} /> : <Clock size={12} />}</span>
                  <div><strong>{e.label}</strong>{e.detail && <p>{e.detail}</p>}<p className="app-small">{new Date(e.at).toLocaleTimeString()}</p></div>
                </li>
              ))}
            </ol>
          </section>
          {runView && d.can_control && (
            <section className="app-card">
              <h2 className="app-card-title">{runView.mode === "collaboration" ? <Bot size={16} /> : <Workflow size={16} />}Run control</h2>
              <RunControls run={runView} onChanged={refresh} compact />
              <Link className="app-btn small" style={{ marginTop: 10 }} href={`/workspace/runs/${runView.id}`}>Open full run view</Link>
            </section>
          )}
          {d.can_control && !active && d.status !== "approved" && can("enquiry.create") && (
            <section className="app-card sunken app-stack">
              <h2 className="app-card-title"><Repeat size={16} />Run again</h2>
              <p className="app-small app-muted">Starting a new run never changes an earlier one. Earlier runs and their exchanges stay in the history.</p>
              <div className="app-row">
                <button className="app-btn small" disabled={start.pending} onClick={async () => { const r = await start.run(d.mode); if (r) { toast("ok", "New run started."); refresh(); } }}><RefreshCw size={14} />New {d.mode} run</button>
                <button className="app-btn small" disabled={start.pending} onClick={async () => { const r = await start.run(otherMode); if (r) { toast("ok", `New ${otherMode} run started.`); router.push(`/workspace/runs/${r.id}`); } }} data-testid="start-other-mode">{otherMode === "collaboration" ? <Bot size={14} /> : <Workflow size={14} />}Try {otherMode === "collaboration" ? "agent collaboration" : "guided workflow"}</button>
              </div>
              {start.error && <Alert tone="danger">{errorMessage(start.error)}</Alert>}
            </section>
          )}
          {d.status === "approved" && d.is_owner && can("enquiry.create") && (
            <section className="app-card sunken app-stack">
              <h2 className="app-card-title"><Repeat size={16} />Order this again</h2>
              <p className="app-small app-muted">Creates a new enquiry from the same request. Compatibility and stock are checked again against today&apos;s catalogue — the earlier answer is not reused.</p>
              <div><button className="app-btn small" disabled={repeat.pending} data-testid="repeat-enquiry" onClick={async () => { const r = await repeat.run(); if (r) { toast("ok", "New enquiry created from this one."); router.push(`/workspace/enquiries/${r.id}`); } }}><Repeat size={14} />Repeat this enquiry</button></div>
              {repeat.error && <Alert tone="danger">{errorMessage(repeat.error)}</Alert>}
            </section>
          )}
          {d.runs.length > 1 && (
            <section className="app-card">
              <h2 className="app-card-title">Run history</h2>
              <div className="app-list app-small">
                {d.runs.map((r) => (
                  <Link key={r.id} href={`/workspace/runs/${r.id}`} className="app-row" style={{ textDecoration: "none", justifyContent: "space-between" }}>
                    <span>{r.mode} · rev {r.revision}</span><RunStatusBadge status={r.status} />
                  </Link>
                ))}
              </div>
            </section>
          )}
          <section className="app-card sunken">
            <dl className="app-kv app-small">
              <dt>Destination</dt><dd>{d.destination.name}</dd>
              <dt>Created</dt><dd>{formatTime(d.created_at)}</dd>
              <dt>Updated</dt><dd>{formatTime(d.updated_at)}</dd>
              <dt>Reference</dt><dd><Ident>{d.id.slice(0, 8)}</Ident></dd>
            </dl>
          </section>
        </aside>
      </div>
    </>
  );
}

function ItemCard({ item }: { item: ItemDetail }): JSX.Element {
  return (
    <div className="app-evidence" data-testid="item-card" data-item-status={item.status}>
      <header>
        <strong dir="auto">{item.quantity ?? "?"} × {item.description}</strong>
        <span className={`app-badge ${item.status === "ready" ? "ok" : item.status === "needs_information" ? "warn" : item.status === "unavailable" ? "danger" : "info"}`}>{item.status === "ready" ? "Matched" : item.status === "needs_information" ? "Needs information" : item.status === "unavailable" ? "No compatible part" : "Checking"}</span>
        {item.quantity_assumed && <span className="app-badge warn" title="No quantity was stated; drafted for one unit">Quantity assumed: 1</span>}
      </header>
      <div className="app-small app-muted">
        Machine: {item.configuration_label ?? (item.model_text ? <Ident>{item.model_text}</Ident> : "not identified")}{item.serial_text && <> · serial <Ident>{item.serial_text}</Ident></>}
      </div>
      {item.identification_note && <div className="app-small app-muted">{item.identification_note}</div>}
      {item.quoted_number_note && <div className="app-small">{item.quoted_number_note}</div>}
      {item.selected && (
        <div className="app-small">
          Compatible part <Ident>{item.selected.part_number}</Ident> — {item.selected.name_en} <span dir="rtl">({item.selected.name_ar})</span>
          <div className="app-muted">Fitment source: <Ident>{item.selected.source_reference}</Ident>{item.selected.superseded_from.length > 0 && <> · replaces <Ident>{item.selected.superseded_from.join(", ")}</Ident></>}</div>
        </div>
      )}
      {item.plan && (
        <div className="app-small">
          {item.plan.message}
          {item.plan.shortage > 0 && <span className="app-badge warn" style={{ marginInlineStart: 6 }}>Short by {item.plan.shortage}</span>}
          <div className="app-muted">Transfer times are estimates from approved routes, not delivery guarantees.</div>
        </div>
      )}
    </div>
  );
}
