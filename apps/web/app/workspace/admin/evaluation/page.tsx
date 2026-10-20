"use client";

import { FlaskConical, Play } from "lucide-react";
import { useCallback, useState, type JSX } from "react";

import { Alert, EmptyState, ErrorState, PageHeader, PermissionDenied, Skeleton, formatTime, useToast } from "@/components/app/ui";
import { errorMessage, useIdempotentAction, useLoad } from "@/lib/hooks";
import { useSession } from "@/lib/session";
import { ws } from "@/lib/workspace";

export default function EvaluationPage(): JSX.Element {
  const { can } = useSession();
  const toast = useToast();
  const runs = useLoad(() => ws.evaluations());
  const corrections = useLoad(() => ws.corrections());
  const [selected, setSelected] = useState<string | null>(null);
  const detail = useLoad(async () => (selected ? ws.evaluation(selected) : null), [selected]);
  const runFn = useCallback(async (key: string) => ws.runEvaluation(key), []);
  const run = useIdempotentAction(runFn);
  if (!can("evaluation.run")) return <PermissionDenied />;
  return (
    <>
      <PageHeader title="Evaluation" description="Runs the labelled synthetic cases in evals/cases.json through the same pipeline enquiries use (fixture, no model calls) and reports exact matches with the denominator." actions={<button className="app-btn primary" disabled={run.pending} onClick={async () => { const r = await run.run(); if (r) { toast("ok", "Evaluation finished."); setSelected(r.id); runs.reload(); } }} data-testid="run-eval"><Play size={15} />Run evaluation</button>} />
      {run.error && <Alert tone="danger">{errorMessage(run.error)}</Alert>}
      <div className="app-split">
        <section>
          {runs.error ? <ErrorState error={runs.error} onRetry={runs.reload} /> : !runs.data ? <Skeleton lines={3} /> : runs.data.length ? (
            <div className="app-table-wrap"><table className="app-table"><thead><tr><th>Run</th><th>Result</th><th>Dataset</th><th>When</th></tr></thead>
              <tbody>{runs.data.map((r) => <tr key={r.id} className="clickable" onClick={() => setSelected(r.id)}><td className="app-mono">{r.id.slice(0, 8)}</td><td><strong>{r.passed} / {r.total}</strong> passed</td><td className="app-small">{r.dataset} <span className="app-mono app-muted">{r.dataset_sha256.slice(0, 10)}</span></td><td className="app-small">{formatTime(r.created_at)}</td></tr>)}</tbody></table></div>
          ) : <EmptyState icon={<FlaskConical size={28} />} title="No evaluation runs" body="Run the evaluation to measure accuracy on the labelled set." />}
          {detail.data && (
            <div className="app-card" style={{ marginTop: 16 }} data-testid="eval-results">
              <h2 className="app-card-title">Per-case results</h2>
              <div className="app-table-wrap"><table className="app-table"><thead><tr><th>Case</th><th>Passed</th><th>Actual status</th><th>Parts</th><th>Clarification</th></tr></thead>
                <tbody>{detail.data.results.map((c) => <tr key={c.case_id}><td className="app-mono">{c.case_id}</td><td>{c.passed ? <span className="app-badge ok">yes</span> : <span className="app-badge danger">no</span>}</td><td>{c.actual.status}</td><td className="app-mono">{c.actual.part_ids.join(", ") || "—"}</td><td>{c.actual.clarification_code}</td></tr>)}</tbody></table></div>
              <p className="app-small app-muted">Failed cases keep the actual output; expected answers are never substituted.</p>
            </div>
          )}
        </section>
        <section className="app-card">
          <h2 className="app-card-title">Reviewer corrections</h2>
          <p className="app-small app-muted">Corrections are not ground truth until a person reviews them and curates an anonymised case.</p>
          {corrections.error ? <ErrorState error={corrections.error} /> : !corrections.data ? <Skeleton lines={2} /> : corrections.data.length ? (
            <div className="app-list app-small">{corrections.data.map((c) => <div key={c.id}><strong>{c.field}</strong>: {c.before ?? "—"} → {c.after} <span className="app-muted">rev {c.revision}</span> {c.reviewed ? <span className="app-badge ok">reviewed</span> : <button className="app-btn small" onClick={async () => { await ws.reviewCorrection(c.id, crypto.randomUUID()); corrections.reload(); }}>Mark reviewed</button>}</div>)}</div>
          ) : <p className="app-muted">No corrections recorded.</p>}
        </section>
      </div>
    </>
  );
}
