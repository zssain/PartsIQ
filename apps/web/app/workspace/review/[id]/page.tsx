"use client";

import { Activity, Bot, CheckCircle2, ClipboardCheck, Database, Gavel, History, StickyNote, UserCheck, XCircle } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useMemo, useState, type JSX } from "react";

import { useCrumb } from "@/components/app/AppShell";
import { Alert, ConfirmDialog, ErrorState, Ident, PageHeader, PermissionDenied, RunStatusBadge, Skeleton, SourceBadge, StatusBadge, formatTime, useToast } from "@/components/app/ui";
import { ApiError } from "@/lib/api";
import { errorMessage, useIdempotentAction, useLoad } from "@/lib/hooks";
import { useSession } from "@/lib/session";
import { ws, type ReviewDetail } from "@/lib/workspace";

const RULES = [
  ["current_revision", "Current revision"], ["catalogue_version", "Active catalogue version"], ["candidate_membership", "Part is a surfaced compatible candidate"],
  ["configuration_membership", "Part fits the identified configuration"], ["source_evidence", "Version-specific fitment citation"], ["quantity", "Quantities and shortage add up"],
  ["allocation", "Allocation within current stock"],
] as const;
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
  const { data, error, loading, reload } = useLoad((signal) => ws.reviewDetail(id, signal), [id]);
  useCrumb(data ? (data.messages[0]?.body ?? "Review").slice(0, 40) : null);
  if (!can("review.queue")) return <PermissionDenied />;
  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (!data) return loading ? <Skeleton lines={10} /> : <ErrorState error={new Error("Not found")} />;
  return <Review d={data} reload={reload} />;
}

function Review({ d, reload }: { d: ReviewDetail; reload: () => void }): JSX.Element {
  const toast = useToast();
  const { can } = useSession();
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
        title="Review"
        kicker={<><StatusBadge status={d.status} /><span>Revision {d.revision}</span>{d.run && <><RunStatusBadge status={d.run.status} /><SourceBadge source={d.run.execution_source} /></>}{d.priority === "urgent" && <span className="app-badge warn">Urgent</span>}</>}
        description={<span dir="auto">{d.messages[0]?.body}</span>}
        actions={<>
          {d.run && <Link className="app-btn" href={`/workspace/runs/${d.run.id}`}><Activity size={15} />{d.mode === "collaboration" ? "Specialist exchanges" : "Run activity"}</Link>}
          <Link className="app-btn" href={`/workspace/enquiries/${d.id}`}>Customer view</Link>
        </>}
      />
      {conflict && (
        <Alert tone="warn" title="This enquiry changed while you were reviewing">
          {conflict} Your reason and notes are kept. <button className="app-btn small" onClick={() => { approve.reset(); reject.reset(); reload(); }}>Reload latest</button>
        </Alert>
      )}
      {!d.catalogue_current && <Alert tone="warn" title="Catalogue changed">The draft was built against an earlier catalogue version; approval will be refused until a new run re-checks it.</Alert>}

      <div className="app-review" style={{ marginTop: 12 }} data-testid="review-workspace">
        {/* -------- AI proposal -------- */}
        <section className="app-card app-region ai" aria-labelledby="region-ai" data-testid="region-ai">
          <p className="app-region-label" id="region-ai"><Bot size={13} /> AI proposal · suggestion only</p>
          <h2 className="app-card-title">Draft reply {d.draft && <span className="app-badge outline">{d.draft.source === "fixture" ? "fixture prose" : d.draft.source === "staff" ? "edited by staff" : "live model prose"}</span>}</h2>
          {d.draft ? <SafeReply html={d.draft.rendered} /> : <p className="app-muted">No draft yet. {d.wait_reason}</p>}
          <p className="app-small app-muted" style={{ marginTop: 8 }}>Prose slots contain no numbers or part identifiers; every fact in the reply is inserted by code from the verified data on the right.</p>
          <h3 className="app-card-title" style={{ marginTop: 14 }}>Extracted request</h3>
          <dl className="app-kv app-small">
            {d.items.map((item) => (
              <div key={item.id} style={{ display: "contents" }}>
                <dt>Item {item.ordinal}</dt>
                <dd dir="auto">{item.quantity ?? "?"} × {item.description}{item.quantity_assumed && <span className="app-badge warn" style={{ marginInlineStart: 6 }}>Quantity assumed: 1 — confirm with customer</span>}<div className="app-muted">model <Ident>{item.model_text ?? "—"}</Ident> · serial <Ident>{item.serial_text ?? "—"}</Ident></div></dd>
              </div>
            ))}
          </dl>
          {d.instructions.length > 0 && (
            <>
              <h3 className="app-card-title" style={{ marginTop: 14 }}>Instructions on the run</h3>
              <ul className="app-small" style={{ margin: 0, paddingInlineStart: 18 }}>{d.instructions.map((i, n) => <li key={n} dir="auto">{i}</li>)}</ul>
              <p className="app-small app-muted">Untrusted input. They cannot change facts, compatibility or approval.</p>
            </>
          )}
        </section>

        {/* -------- Database evidence -------- */}
        <section className="app-card app-region db" aria-labelledby="region-db" data-testid="region-db">
          <p className="app-region-label" id="region-db"><Database size={13} /> Database evidence</p>
          {d.items.map((item) => (
            <div key={item.id} className="app-evidence" style={{ marginBottom: 10 }} data-testid="evidence-item">
              <header><strong>Item {item.ordinal}</strong><span className="app-small app-muted">{item.configuration_label ?? "configuration not identified"}</span></header>
              {item.identification_note && <div className="app-small app-muted">{item.identification_note}</div>}
              {item.selected ? (
                <div className="app-small">
                  <div>Selected <Ident>{item.selected.part_number}</Ident> — {item.selected.name_en} <span dir="rtl">/ {item.selected.name_ar}</span> <span className="app-badge outline">{item.selected.selection_source === "customer_choice" ? "customer choice" : "compatibility search"}</span></div>
                  <div className="app-muted">Fitment: <Ident>{item.selected.source_reference}</Ident></div>
                  {item.selected.superseded_from.length > 0 && <div className="app-muted">Supersedes <Ident>{item.selected.superseded_from.join(" → ")}</Ident> (successor has its own fitment)</div>}
                  <div className="app-muted">Match basis: {item.selected.reasons.join(", ") || "—"}{item.selected.matched_terms.length ? ` · terms: ${item.selected.matched_terms.join(", ")}` : ""}</div>
                </div>
              ) : <div className="app-small">{item.clarification_text ?? "No compatible selection."}</div>}
              {item.candidates.length > 1 && (
                <details className="app-small"><summary>Compatible candidates ({item.candidates.length})</summary>
                  <table className="app-table" style={{ marginTop: 6 }}><thead><tr><th>Part</th><th>Score</th><th>Source</th></tr></thead>
                    <tbody>{item.candidates.map((c) => <tr key={c.part_id}><td><Ident>{c.part_number}</Ident> {c.name_en}</td><td>{c.score.toFixed(2)}</td><td className="app-mono">{c.source_reference}</td></tr>)}</tbody></table>
                  <p className="app-muted">Score is a ranking signal over compatible parts only — not a probability, and similarity never establishes fitment.</p>
                </details>
              )}
              {item.plan && (
                <div className="app-small">
                  <strong>Stock plan:</strong> {item.plan.message}
                  <ul style={{ margin: "4px 0 0", paddingInlineStart: 18 }}>
                    {item.plan.lines.map((l, i) => <li key={i}>{l.quantity} from {l.warehouse_name} · {l.transfer_days ? `~${l.transfer_days} day transfer (estimate)` : "local"} · observed {new Date(l.observed_at).toLocaleTimeString()}</li>)}
                  </ul>
                  {item.plan.shortage > 0 && <span className="app-badge warn">Shortage {item.plan.shortage}</span>}
                </div>
              )}
            </div>
          ))}
          <h3 className="app-card-title" style={{ marginTop: 6 }}>Verification <span className={`app-badge ${d.verification?.passed ? "ok" : d.verification ? "danger" : ""}`}>{d.verification ? (d.verification.passed ? "Passed" : "Failed") : "Not run"}</span></h3>
          <ul className="app-small" style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 4 }} data-testid="verification-rules">
            {RULES.map(([key, label]) => (
              <li key={key} className="app-row" style={{ gap: 6 }}>
                {!d.verification ? <span className="app-dot" style={{ color: "var(--app-border-strong)" }} /> : failed.has(key) ? <XCircle size={14} color="var(--app-danger)" /> : <CheckCircle2 size={14} color="var(--app-ok)" />}
                {label}
              </li>
            ))}
          </ul>
          {d.verification?.failures.map((f, i) => <p key={i} className="app-small" style={{ color: "var(--app-danger)" }}>{f.code}: {f.detail}</p>)}
          {d.evidence && <p className="app-small app-muted">Stock evidence observed {formatTime(d.evidence.stock[0]?.updated_at)}; approval re-reads stock and re-runs these rules.</p>}
        </section>

        {/* -------- Human decision -------- */}
        <section className="app-card app-region human" aria-labelledby="region-human" data-testid="region-human">
          <p className="app-region-label" id="region-human"><Gavel size={13} /> Human decision</p>
          {decided ? (
            <div data-testid="decision-outcome">
              <Alert tone={decided.kind === "approved" ? "ok" : "warn"} title={decided.kind === "approved" ? "Approved and published" : "Rejected"}>
                Revision {decided.revision} · {formatTime(decided.at)}{decided.reason ? ` · “${decided.reason}”` : ""}
              </Alert>
            </div>
          ) : ready ? (
            <div className="app-stack">
              <p className="app-small">Approving publishes this reply to the customer exactly once. Stock and evidence are re-checked at that moment.</p>
              <button className="app-btn primary" onClick={() => setConfirmApprove(true)} disabled={approve.pending || !can("review.decide")} data-testid="approve"><CheckCircle2 size={16} />Approve & publish</button>
              <label className="app-field"><span>Or return it with a reason</span><textarea className="app-textarea" style={{ minHeight: 70 }} value={reason} onChange={(e) => setReason(e.target.value)} maxLength={1000} data-testid="reject-reason" placeholder="e.g. Please confirm the serial with the customer." /></label>
              <button className="app-btn danger" disabled={reject.pending || !reason.trim() || !can("review.decide")} onClick={async () => { const r = await reject.run(reason.trim()); if (r) { toast("ok", "Rejected. Nothing was published."); reload(); } }} data-testid="reject"><XCircle size={15} />Reject</button>
              {(approve.error || reject.error) && !conflict && <Alert tone="danger">{errorMessage(approve.error ?? reject.error)}</Alert>}
            </div>
          ) : (
            <Alert tone="info">{d.status === "awaiting_review" ? "The draft did not pass verification; it cannot be approved." : d.wait_reason ?? "Nothing to decide yet."}</Alert>
          )}

          <h3 className="app-card-title" style={{ marginTop: 16 }}><UserCheck size={15} />Assignment</h3>
          <p className="app-small">{d.assigned_label ? <>Assigned to <strong>{d.assigned_label}</strong></> : "Unassigned"}</p>
          {d.can_assign && (
            <select className="app-select" aria-label="Assign reviewer" value={d.assigned_to ?? ""} disabled={assign.pending} onChange={async (e) => { const r = await assign.run(e.target.value || null); if (r) { toast("ok", "Assignment updated."); reload(); } }} data-testid="assign">
              <option value="">Unassigned</option>
              {d.reviewers.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
            </select>
          )}
          {assign.error && <Alert tone="danger">{errorMessage(assign.error)}</Alert>}

          <h3 className="app-card-title" style={{ marginTop: 16 }}><StickyNote size={15} />Internal notes <span className="app-badge outline">staff only</span></h3>
          <div className="app-list app-small">{d.notes.length === 0 ? <span className="app-muted">No notes.</span> : d.notes.map((n) => <div key={n.id}><strong>{n.author_label}</strong> · {formatTime(n.created_at)}<div dir="auto">{n.body}</div></div>)}</div>
          <form className="app-stack" onSubmit={async (e) => { e.preventDefault(); if (!note.trim()) return; const r = await addNote.run(note.trim()); if (r) { setNote(""); reload(); } }}>
            <textarea className="app-textarea" style={{ minHeight: 60 }} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Visible to staff only" maxLength={4000} />
            <div><button className="app-btn small" disabled={addNote.pending || !note.trim()}>Add note</button></div>
          </form>

          <h3 className="app-card-title" style={{ marginTop: 16 }}><History size={15} />History</h3>
          <ul className="app-small" style={{ margin: 0, paddingInlineStart: 18 }}>
            <li>Revisions: {d.revisions.join(", ")}</li>
            {d.review_ready_at && <li>Ready for review {formatTime(d.review_ready_at)}</li>}
            {d.decisions.map((x) => <li key={x.id}>{x.kind} rev {x.revision} by {x.actor_label} · {formatTime(x.at)}</li>)}
            <li>Due {formatTime(d.due_at)}</li>
          </ul>
        </section>
      </div>
      <ConfirmDialog
        open={confirmApprove}
        title="Approve and publish?"
        body={<>The customer will see this recommendation. Revision {d.revision}, draft <Ident>{d.draft?.id.slice(0, 8)}</Ident>.</>}
        confirmLabel="Approve & publish"
        pending={approve.pending}
        onCancel={() => setConfirmApprove(false)}
        onConfirm={async () => { setConfirmApprove(false); const r = await approve.run(); if (r) { toast("ok", r.already_applied ? "Already approved — nothing was published twice." : "Approved and published."); reload(); } }}
      />
      <p className="app-small app-muted" style={{ marginTop: 12 }}><ClipboardCheck size={12} /> Approval carries the expected revision and draft id; a stale request is refused and your inputs are kept.</p>
    </>
  );
}
