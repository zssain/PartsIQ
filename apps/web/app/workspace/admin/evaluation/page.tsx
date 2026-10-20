"use client";

import { FlaskConical, Play } from "lucide-react";
import { useCallback, useState, type JSX } from "react";

import { Alert, EmptyState, ErrorState, Ident, PageHeader, PermissionDenied, Skeleton, useDates, useToast } from "@/components/app/ui";
import { useLabel, useT, useTx } from "@/lib/app-i18n";
import { errorMessage, useIdempotentAction, useLoad } from "@/lib/hooks";
import { useSession } from "@/lib/session";
import { ws } from "@/lib/workspace";

export default function EvaluationPage(): JSX.Element {
  const { can } = useSession();
  const toast = useToast();
  const t = useT();
  const tx = useTx();
  const label = useLabel();
  const { time } = useDates();
  const runs = useLoad(() => ws.evaluations());
  const corrections = useLoad(() => ws.corrections());
  const [selected, setSelected] = useState<string | null>(null);
  const detail = useLoad(async () => (selected ? ws.evaluation(selected) : null), [selected]);
  const runFn = useCallback(async (key: string) => ws.runEvaluation(key), []);
  const run = useIdempotentAction(runFn);
  if (!can("evaluation.run")) return <PermissionDenied />;
  return (
    <>
      <PageHeader title={t("nav.evaluation")} description={t("eval.desc")} actions={<button className="app-btn primary" disabled={run.pending} onClick={async () => { const r = await run.run(); if (r) { toast("ok", t("eval.finished")); setSelected(r.id); runs.reload(); } }} data-testid="run-eval"><Play size={15} />{t("eval.run")}</button>} />
      {run.error && <Alert tone="danger">{errorMessage(run.error)}</Alert>}
      <div className="app-split">
        <section>
          {runs.error ? <ErrorState error={runs.error} onRetry={runs.reload} /> : !runs.data ? <Skeleton lines={3} /> : runs.data.length ? (
            <div className="app-table-wrap"><table className="app-table"><thead><tr><th>{t("eval.thRun")}</th><th>{t("eval.thResult")}</th><th>{t("eval.thDataset")}</th><th>{t("eval.thWhen")}</th></tr></thead>
              <tbody>{runs.data.map((r) => <tr key={r.id} className="clickable" onClick={() => setSelected(r.id)}><td><Ident>{r.id.slice(0, 8)}</Ident></td><td>{tx("eval.passedOf", { passed: <strong>{r.passed}</strong>, total: <strong>{r.total}</strong> })}</td><td className="app-small"><bdi>{r.dataset}</bdi> <bdi className="app-mono app-muted">{r.dataset_sha256.slice(0, 10)}</bdi></td><td className="app-small">{time(r.created_at)}</td></tr>)}</tbody></table></div>
          ) : <EmptyState icon={<FlaskConical size={28} />} title={t("eval.empty")} body={t("eval.emptyBody")} />}
          {detail.data && (
            <div className="app-card" style={{ marginTop: 16 }} data-testid="eval-results">
              <h2 className="app-card-title">{t("eval.perCase")}</h2>
              <div className="app-table-wrap"><table className="app-table"><thead><tr><th>{t("eval.thCase")}</th><th>{t("eval.thPassed")}</th><th>{t("eval.thActual")}</th><th>{t("eval.thParts")}</th><th>{t("eval.thClarification")}</th></tr></thead>
                <tbody>{detail.data.results.map((c) => <tr key={c.case_id}><td><Ident>{c.case_id}</Ident></td><td>{c.passed ? <span className="app-badge ok">{t("common.yes")}</span> : <span className="app-badge danger">{t("common.no")}</span>}</td><td>{label("status", c.actual.status, c.actual.status)}</td><td><Ident>{c.actual.part_ids.join(", ") || "—"}</Ident></td><td>{c.actual.clarification_code && <Ident>{c.actual.clarification_code}</Ident>}</td></tr>)}</tbody></table></div>
              <p className="app-small app-muted">{t("eval.failedNote")}</p>
            </div>
          )}
        </section>
        <section className="app-card">
          <h2 className="app-card-title">{t("eval.corrections")}</h2>
          <p className="app-small app-muted">{t("eval.correctionsNote")}</p>
          {corrections.error ? <ErrorState error={corrections.error} /> : !corrections.data ? <Skeleton lines={2} /> : corrections.data.length ? (
            <div className="app-list app-small">{corrections.data.map((c) => <div key={c.id}><bdi className="app-mono"><strong>{c.field}</strong></bdi>: <bdi dir="auto">{c.before ?? "—"} → {c.after}</bdi> <span className="app-muted">{tx("common.rev", { rev: <bdi>{c.revision}</bdi> })}</span> {c.reviewed ? <span className="app-badge ok">{t("eval.reviewed")}</span> : <button className="app-btn small" onClick={async () => { await ws.reviewCorrection(c.id, crypto.randomUUID()); corrections.reload(); }}>{t("eval.markReviewed")}</button>}</div>)}</div>
          ) : <p className="app-muted">{t("eval.noCorrections")}</p>}
        </section>
      </div>
    </>
  );
}
