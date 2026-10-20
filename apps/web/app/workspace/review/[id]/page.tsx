"use client";

import { Activity, Bot, CheckCircle2, ClipboardCheck, Database, Gavel, History, StickyNote, UserCheck, XCircle } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useMemo, useState, type JSX } from "react";

import { useCrumb } from "@/components/app/AppShell";
import { Alert, ConfirmDialog, ErrorState, Ident, PageHeader, PermissionDenied, RunStatusBadge, Skeleton, SourceBadge, StatusBadge, useDates, useToast } from "@/components/app/ui";
import { ApiError } from "@/lib/api";
import { useLabel, useT, useTx, type TKey } from "@/lib/app-i18n";
import { errorMessage, useIdempotentAction, useLoad } from "@/lib/hooks";
import { useSession } from "@/lib/session";
import { ws, type ReviewDetail } from "@/lib/workspace";

const RULES = ["current_revision", "catalogue_version", "candidate_membership", "configuration_membership", "source_evidence", "quantity", "allocation"] as const;
const FAILURE_RULE: Record<string, string> = {
  STALE_REVISION: "current_revision", STALE_CATALOGUE: "catalogue_version", INCOMPATIBLE: "configuration_membership", UNRESOLVED_ITEM: "candidate_membership",
  MISSING_EVIDENCE: "source_evidence", INVALID_QUANTITY: "quantity", OVERALLOCATION: "allocation", STALE_STOCK: "allocation",
};

/** Render the code-generated reply HTML through an element allowlist (defence in depth). */
function SafeReply({ html }: { html: string }): JSX.Element {
  const nodes = useMemo(() => {
    if (typeof window === "undefined") return null;
    const doc = new DOMParser().parseFromString(html, "text/html");
    const allowed = new Set(["DIV", "P", "UL", "OL", "LI", "STRONG", "EM", "BDI", "SPAN", "BR"]);
    const walk = (node: Node, key: string): React.ReactNode => {
      if (node.nodeType === Node.TEXT_NODE) return node.textContent;
      if (node.nodeType !== Node.ELEMENT_NODE) return null;
      const el = node as Element;
      const children = Array.from(el.childNodes).map((c, i) => walk(c, `${key}.${i}`));
      if (!allowed.has(el.tagName)) return <span key={key}>{children}</span>;
      const Tag = el.tagName.toLowerCase() as "div";
      return <Tag key={key} dir={el.getAttribute("dir") ?? undefined}>{el.tagName === "BR" ? null : children}</Tag>;
    };
    return Array.from(doc.body.childNodes).map((n, i) => walk(n, String(i)));
  }, [html]);
  return <div className="app-draft" data-testid="draft-reply">{nodes}</div>;
}

export default function ReviewPage(): JSX.Element {
  const { id } = useParams<{ id: string }>();
  const { can } = useSession();
  const t = useT();
  const { data, error, loading, reload } = useLoad((signal) => ws.reviewDetail(id, signal), [id]);
  useCrumb(data ? (data.messages[0]?.body ?? t("review.title")).slice(0, 40) : null);
  if (!can("review.queue")) return <PermissionDenied />;
  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (!data) return loading ? <Skeleton lines={10} /> : <ErrorState error={new Error("Not found")} />;
  return <Review d={data} reload={reload} />;
}

function Review({ d, reload }: { d: ReviewDetail; reload: () => void }): JSX.Element {
  const toast = useToast();
  const { can } = useSession();
  const t = useT();
  const tx = useTx();
  const label = useLabel();
  const { time, clock } = useDates();
  const rev = (n: number) => <bdi>{n}</bdi>;
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [confirmApprove, setConfirmApprove] = useState(false);
  const decided = d.decision;
  const approveFn = useCallback(async (key: string) => ws.approve(d.id, { expected_revision: d.revision, draft_id: d.draft?.id ?? "" }, key), [d.id, d.revision, d.draft?.id]);
  const rejectFn = useCallback(async (key: string, text: string) => ws.reject(d.id, { expected_revision: d.revision, reason: text }, key), [d.id, d.revision]);
  const noteFn = useCallback(async (key: string, text: string) => ws.note(d.id, text, key), [d.id]);
  const assignFn = useCallback(async (key: string, who: string | null) => ws.assign(d.id, who, d.revision, key), [d.id, d.revision]);
  const approve = useIdempotentAction(approveFn);
  const reject = useIdempotentAction(rejectFn);
  const addNote = useIdempotentAction(noteFn);
  const assign = useIdempotentAction(assignFn);

  // A 409 means the enquiry changed underneath the reviewer: derived from the action errors.
  const decisionError = approve.error ?? reject.error;
  const conflict = decisionError instanceof ApiError && decisionError.status === 409 ? decisionError.message : null;

  const failed = new Set((d.verification?.failures ?? []).map((f) => FAILURE_RULE[f.code] ?? f.code));
  const ready = d.can_decide && d.verification?.passed && d.draft;

  return (
    <>
      <PageHeader
        title={t("review.title")}
        kicker={<><StatusBadge status={d.status} /><span>{tx("common.revision", { rev: rev(d.revision) })}</span>{d.run && <><RunStatusBadge status={d.run.status} /><SourceBadge source={d.run.execution_source} /></>}{d.priority === "urgent" && <span className="app-badge warn">{t("common.urgent")}</span>}</>}
        description={<span dir="auto">{d.messages[0]?.body}</span>}
        actions={<>
          {d.run && <Link className="app-btn" href={`/workspace/runs/${d.run.id}`}><Activity size={15} />{d.mode === "collaboration" ? t("detail.exchanges") : t("detail.activity")}</Link>}
          <Link className="app-btn" href={`/workspace/enquiries/${d.id}`}>{t("review.customerView")}</Link>
        </>}
      />
      {conflict && (
        <Alert tone="warn" title={t("review.conflictTitle")}>
          <span dir="auto">{conflict}</span> {t("review.conflictKept")} <button className="app-btn small" onClick={() => { approve.reset(); reject.reset(); reload(); }}>{t("review.reloadLatest")}</button>
        </Alert>
      )}
      {!d.catalogue_current && <Alert tone="warn" title={t("detail.catChanged")}>{t("review.catChangedBody")}</Alert>}

      <div className="app-review" style={{ marginTop: 12 }} data-testid="review-workspace">
        {/* -------- AI proposal -------- */}
        <section className="app-card app-region ai" aria-labelledby="region-ai" data-testid="region-ai">
          <p className="app-region-label" id="region-ai"><Bot size={13} /> {t("review.regionAi")}</p>
          <h2 className="app-card-title">{t("review.draftReply")} {d.draft && <span className="app-badge outline">{t(d.draft.source === "fixture" ? "review.draftSource.fixture" : d.draft.source === "staff" ? "review.draftSource.staff" : "review.draftSource.live")}</span>}</h2>
          {d.draft ? <SafeReply html={d.draft.rendered} /> : <p className="app-muted">{t("review.noDraft")} {d.wait_reason && <span dir="auto">{d.wait_reason}</span>}</p>}
          <p className="app-small app-muted" style={{ marginTop: 8 }}>{t("review.proseNote")}</p>
          <h3 className="app-card-title" style={{ marginTop: 14 }}>{t("review.extracted")}</h3>
          <dl className="app-kv app-small">
            {d.items.map((item) => (
              <div key={item.id} style={{ display: "contents" }}>
                <dt>{t("review.item", { n: item.ordinal })}</dt>
                <dd><span dir="auto">{item.quantity ?? "?"} × {item.description}</span>{item.quantity_assumed && <span className="app-badge warn" style={{ marginInlineStart: 6 }}>{t("review.qtyAssumed")}</span>}<div className="app-muted">{tx("review.modelSerial", { model: <Ident>{item.model_text ?? "—"}</Ident>, serial: <Ident>{item.serial_text ?? "—"}</Ident> })}</div></dd>
              </div>
            ))}
          </dl>
          {d.instructions.length > 0 && (
            <>
              <h3 className="app-card-title" style={{ marginTop: 14 }}>{t("review.instructions")}</h3>
              <ul className="app-small" style={{ margin: 0, paddingInlineStart: 18 }}>{d.instructions.map((i, n) => <li key={n} dir="auto">{i}</li>)}</ul>
              <p className="app-small app-muted">{t("review.instructionsNote")}</p>
            </>
          )}
        </section>

        {/* -------- Database evidence -------- */}
        <section className="app-card app-region db" aria-labelledby="region-db" data-testid="region-db">
          <p className="app-region-label" id="region-db"><Database size={13} /> {t("review.regionDb")}</p>
          {d.items.map((item) => (
            <div key={item.id} className="app-evidence" style={{ marginBottom: 10 }} data-testid="evidence-item">
              <header><strong>{t("review.item", { n: item.ordinal })}</strong><span className="app-small app-muted">{item.configuration_label ? <bdi>{item.configuration_label}</bdi> : t("review.configNotIdentified")}</span></header>
              {item.identification_note && <div className="app-small app-muted" dir="auto">{item.identification_note}</div>}
              {item.selected ? (
                <div className="app-small">
                  <div>{tx("review.selected", { part: <Ident>{item.selected.part_number}</Ident>, name: <><bdi>{item.selected.name_en}</bdi> <bdi dir="rtl">/ {item.selected.name_ar}</bdi></> })} <span className="app-badge outline">{t(item.selected.selection_source === "customer_choice" ? "review.selSource.customer_choice" : "review.selSource.search")}</span></div>
                  <div className="app-muted">{tx("review.fitment", { ref: <Ident>{item.selected.source_reference}</Ident> })}</div>
                  {item.selected.superseded_from.length > 0 && <div className="app-muted">{tx("review.supersedes", { parts: <Ident>{item.selected.superseded_from.join(" → ")}</Ident> })}</div>}
                  <div className="app-muted">{tx("review.matchBasis", { reasons: <bdi>{item.selected.reasons.join(", ") || "—"}</bdi> })}{item.selected.matched_terms.length > 0 && tx("review.terms", { terms: <bdi>{item.selected.matched_terms.join(", ")}</bdi> })}</div>
                </div>
              ) : <div className="app-small" dir="auto">{item.clarification_text ?? t("review.noSelection")}</div>}
              {item.candidates.length > 1 && (
                <details className="app-small"><summary>{t("review.candidates", { n: item.candidates.length })}</summary>
                  <table className="app-table" style={{ marginTop: 6 }}><thead><tr><th>{t("review.thPart")}</th><th>{t("review.thScore")}</th><th>{t("review.thSource")}</th></tr></thead>
                    <tbody>{item.candidates.map((c) => <tr key={c.part_id}><td><Ident>{c.part_number}</Ident> <bdi>{c.name_en}</bdi></td><td>{c.score.toFixed(2)}</td><td><Ident>{c.source_reference}</Ident></td></tr>)}</tbody></table>
                  <p className="app-muted">{t("review.scoreNote")}</p>
                </details>
              )}
              {item.plan && (
                <div className="app-small">
                  <strong>{t("review.stockPlan")}</strong> <span dir="auto">{item.plan.message}</span>
                  <ul style={{ margin: "4px 0 0", paddingInlineStart: 18 }}>
                    {item.plan.lines.map((l, i) => <li key={i}>{tx("review.planLine", { qty: l.quantity, warehouse: <bdi>{l.warehouse_name}</bdi>, transfer: l.transfer_days ? t("review.transferDays", { days: l.transfer_days }) : t("review.local"), time: clock(l.observed_at) })}</li>)}
                  </ul>
                  {item.plan.shortage > 0 && <span className="app-badge warn">{t("review.shortage", { n: item.plan.shortage })}</span>}
                </div>
              )}
            </div>
          ))}
          <h3 className="app-card-title" style={{ marginTop: 6 }}>{t("review.verification")} <span className={`app-badge ${d.verification?.passed ? "ok" : d.verification ? "danger" : ""}`}>{d.verification ? (d.verification.passed ? t("review.passed") : t("review.failed")) : t("review.notRun")}</span></h3>
          <ul className="app-small" style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 4 }} data-testid="verification-rules">
            {RULES.map((key) => (
              <li key={key} className="app-row" style={{ gap: 6 }}>
                {!d.verification ? <span className="app-dot" style={{ color: "var(--app-border-strong)" }} /> : failed.has(key) ? <XCircle size={14} color="var(--app-danger)" /> : <CheckCircle2 size={14} color="var(--app-ok)" />}
                {t(`review.rule.${key}` as TKey)}
              </li>
            ))}
          </ul>
          {d.verification?.failures.map((f, i) => <p key={i} className="app-small" style={{ color: "var(--app-danger)" }}><Ident>{f.code}</Ident>: <span dir="auto">{f.detail}</span></p>)}
          {d.evidence && <p className="app-small app-muted">{t("review.stockObserved", { time: time(d.evidence.stock[0]?.updated_at) })}</p>}
        </section>

        {/* -------- Human decision -------- */}
        <section className="app-card app-region human" aria-labelledby="region-human" data-testid="region-human">
          <p className="app-region-label" id="region-human"><Gavel size={13} /> {t("review.regionHuman")}</p>
          {decided ? (
            <div data-testid="decision-outcome">
              <Alert tone={decided.kind === "approved" ? "ok" : "warn"} title={decided.kind === "approved" ? t("review.approvedPublished") : t("review.rejected")}>
                {tx("common.revision", { rev: rev(decided.revision) })} · {time(decided.at)}{decided.reason ? tx("review.decisionReason", { reason: <bdi dir="auto">{decided.reason}</bdi> }) : ""}
              </Alert>
            </div>
          ) : ready ? (
            <div className="app-stack">
              <p className="app-small">{t("review.approveNote")}</p>
              <button className="app-btn primary" onClick={() => setConfirmApprove(true)} disabled={approve.pending || !can("review.decide")} data-testid="approve"><CheckCircle2 size={16} />{t("review.approve")}</button>
              <label className="app-field"><span>{t("review.returnLabel")}</span><textarea className="app-textarea" style={{ minHeight: 70 }} value={reason} onChange={(e) => setReason(e.target.value)} maxLength={1000} data-testid="reject-reason" placeholder={t("review.reasonPlaceholder")} dir="auto" /></label>
              <button className="app-btn danger" disabled={reject.pending || !reason.trim() || !can("review.decide")} onClick={async () => { const r = await reject.run(reason.trim()); if (r) { toast("ok", t("review.rejectedToast")); reload(); } }} data-testid="reject"><XCircle size={15} />{t("review.reject")}</button>
              {(approve.error || reject.error) && !conflict && <Alert tone="danger">{errorMessage(approve.error ?? reject.error)}</Alert>}
            </div>
          ) : (
            <Alert tone="info">{d.status === "awaiting_review" ? t("review.notVerified") : d.wait_reason ? <span dir="auto">{d.wait_reason}</span> : t("review.nothing")}</Alert>
          )}

          <h3 className="app-card-title" style={{ marginTop: 16 }}><UserCheck size={15} />{t("review.assignment")}</h3>
          <p className="app-small">{d.assigned_label ? tx("review.assignedTo", { name: <strong><bdi>{d.assigned_label}</bdi></strong> }) : t("common.unassigned")}</p>
          {d.can_assign && (
            <select className="app-select" aria-label={t("review.assignAria")} value={d.assigned_to ?? ""} disabled={assign.pending} onChange={async (e) => { const r = await assign.run(e.target.value || null); if (r) { toast("ok", t("review.assignToast")); reload(); } }} data-testid="assign">
              <option value="">{t("common.unassigned")}</option>
              {d.reviewers.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
            </select>
          )}
          {assign.error && <Alert tone="danger">{errorMessage(assign.error)}</Alert>}

          <h3 className="app-card-title" style={{ marginTop: 16 }}><StickyNote size={15} />{t("review.notes")} <span className="app-badge outline">{t("review.staffOnly")}</span></h3>
          <div className="app-list app-small">{d.notes.length === 0 ? <span className="app-muted">{t("review.noNotes")}</span> : d.notes.map((n) => <div key={n.id}><strong><bdi>{n.author_label}</bdi></strong> · {time(n.created_at)}<div dir="auto">{n.body}</div></div>)}</div>
          <form className="app-stack" onSubmit={async (e) => { e.preventDefault(); if (!note.trim()) return; const r = await addNote.run(note.trim()); if (r) { setNote(""); reload(); } }}>
            <textarea className="app-textarea" style={{ minHeight: 60 }} value={note} onChange={(e) => setNote(e.target.value)} placeholder={t("review.notePlaceholder")} maxLength={4000} dir="auto" data-testid="review-note" />
            <div><button className="app-btn small" disabled={addNote.pending || !note.trim()}>{t("review.addNote")}</button></div>
          </form>

          <h3 className="app-card-title" style={{ marginTop: 16 }}><History size={15} />{t("review.history")}</h3>
          <ul className="app-small" style={{ margin: 0, paddingInlineStart: 18 }}>
            <li>{tx("review.revisions", { list: <bdi>{d.revisions.join(", ")}</bdi> })}</li>
            {d.review_ready_at && <li>{t("review.readyAt", { time: time(d.review_ready_at) })}</li>}
            {d.decisions.map((x) => <li key={x.id}>{tx("review.historyLine", { kind: label("decisionKind", x.kind), rev: rev(x.revision), actor: <bdi>{x.actor_label}</bdi>, time: time(x.at) })}</li>)}
            <li>{t("review.due", { time: time(d.due_at) })}</li>
          </ul>
        </section>
      </div>
      <ConfirmDialog
        open={confirmApprove}
        title={t("review.confirmTitle")}
        body={tx("review.confirmBody", { rev: rev(d.revision), draft: <Ident>{d.draft?.id.slice(0, 8)}</Ident> })}
        confirmLabel={t("review.approve")}
        pending={approve.pending}
        onCancel={() => setConfirmApprove(false)}
        onConfirm={async () => { setConfirmApprove(false); const r = await approve.run(); if (r) { toast("ok", r.already_applied ? t("review.alreadyApproved") : t("review.approvedToast")); reload(); } }}
      />
      <p className="app-small app-muted" style={{ marginTop: 12 }}><ClipboardCheck size={12} /> {t("review.footer")}</p>
    </>
  );
}
