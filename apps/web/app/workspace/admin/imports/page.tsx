"use client";

import { CheckCircle2, Download, FileUp, Rocket, ShieldAlert } from "lucide-react";
import { useCallback, useRef, useState, type JSX } from "react";

import { Alert, ConfirmDialog, EmptyState, ErrorState, PageHeader, PermissionDenied, Skeleton, formatTime, useToast } from "@/components/app/ui";
import { errorMessage, useIdempotentAction, useLoad } from "@/lib/hooks";
import { useSession } from "@/lib/session";
import { ws, type ImportPreview } from "@/lib/workspace";

const TEMPLATE = `entity_type,part_number,name_en,name_ar,category,unit_of_measure,brand,model_code,config_code,quantity_per_unit,source_reference
parts,VP-AF-9999,Heavy duty air filter,فلتر هواء ثقيل,filters,EA,,,,,
part_compatibility,VP-AF-9999,,,,,Veltrano Power,VP-20,A,1,"SYNTH-VP-PB-VP-20 rev 7, section FILTERS"
`;
const INVALID_SAMPLE = `entity_type,part_number,name_en,name_ar,category,unit_of_measure
parts,=HYPERLINK("http://x"),Bad row,سيء,filters,EA
widgets,XX-1,,,,
parts,VP-ZZ-1,,,,
`;

export default function ImportsPage(): JSX.Element {
  const { can, identity } = useSession();
  const toast = useToast();
  const list = useLoad(() => ws.imports());
  const [active, setActive] = useState<ImportPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const [confirm, setConfirm] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const publishFn = useCallback(async (key: string) => ws.publishImport(active!.id, active!.content_sha256 ?? "", active!.active_version_id, key), [active]);
  const publish = useIdempotentAction(publishFn);
  if (!can("catalogue.import")) return <PermissionDenied />;

  const run = async (filename: string, text: string) => {
    setBusy(true); setErr(null);
    try {
      const staged = await ws.stageImport(filename, new Blob([text]).size, crypto.randomUUID());
      await ws.uploadImport(staged.id, text);
      await ws.validateImport(staged.id);
      setActive(await ws.importPreview(staged.id));
      list.reload();
    } catch (e) { setErr(e); } finally { setBusy(false); }
  };
  const blocking = active?.issues.filter((i) => i.code !== "UNKNOWN_COLUMN") ?? [];
  return (
    <>
      <PageHeader title="Catalogue imports" description={<>Upload a CSV, review the dry-run report, then publish a new catalogue version. Cells are treated as text: formulas and macros are never evaluated.{identity?.kind === "demo" ? " In the demo, publishing changes only your sandbox catalogue." : ""}</>} />
      <div className="app-row" style={{ marginBottom: 14 }}>
        <input ref={fileRef} type="file" accept=".csv,text/csv" hidden onChange={async (e) => { const f = e.target.files?.[0]; if (f) await run(f.name, await f.text()); e.target.value = ""; }} />
        <button className="app-btn primary" disabled={busy} onClick={() => fileRef.current?.click()}><FileUp size={15} />Upload CSV</button>
        <button className="app-btn" disabled={busy} onClick={() => run("valid-sample.csv", TEMPLATE)} data-testid="import-valid">Try a valid sample</button>
        <button className="app-btn" disabled={busy} onClick={() => run("invalid-sample.csv", INVALID_SAMPLE)} data-testid="import-invalid">Try an invalid sample</button>
        <a className="app-btn ghost" href={`data:text/csv;charset=utf-8,${encodeURIComponent(TEMPLATE)}`} download="partsiq-import-template.csv"><Download size={15} />Template</a>
      </div>
      {busy && <Skeleton lines={3} />}
      {err !== null && <ErrorState error={err} />}
      {active && (
        <section className="app-card app-stack" data-testid="import-report" data-state={active.state}>
          <h2 className="app-card-title">{active.filename}<span className={`app-badge ${active.state === "validated" ? "ok" : active.state === "published" ? "accent" : "danger"}`}>{active.state}</span></h2>
          <p className="app-small app-muted">{active.row_count} rows · content <span className="app-mono">{active.content_sha256?.slice(0, 12)}</span> · base version <span className="app-mono">{active.base_version_id?.slice(0, 8)}</span>{!active.base_is_active && " (no longer active — re-validate)"}</p>
          {blocking.length ? (
            <>
              <Alert tone="danger" title={`${blocking.length} blocking issue(s) — nothing can be published`} />
              <div className="app-table-wrap"><table className="app-table" data-testid="import-issues"><thead><tr><th>Row</th><th>Field</th><th>Code</th><th>Message</th></tr></thead>
                <tbody>{active.issues.map((i, n) => <tr key={n}><td>{i.row_number || "—"}</td><td className="app-mono">{i.field}</td><td><span className="app-badge danger">{i.code}</span></td><td className="app-small">{i.message}</td></tr>)}</tbody></table></div>
            </>
          ) : (
            <>
              <Alert tone="ok" title="Dry run passed">Schema, references, serial-range overlap and supersession checks all passed against the active version.</Alert>
              <dl className="app-kv app-small">
                <dt>Added</dt><dd>{Object.entries(active.preview.added ?? {}).map(([k, v]) => `${v} ${k}`).join(", ") || "—"}</dd>
                <dt>Changed</dt><dd>{Object.entries(active.preview.changed ?? {}).map(([k, v]) => `${v} ${k}`).join(", ") || "—"}</dd>
              </dl>
              {active.preview.samples && <ul className="app-small" style={{ margin: 0, paddingInlineStart: 18 }}>{active.preview.samples.map((s) => <li key={s.row_number}>Row {s.row_number}: {s.action} {s.entity_type} — {s.summary}</li>)}</ul>}
              {active.state === "validated" && <div><button className="app-btn primary" disabled={!can("catalogue.publish") || publish.pending} onClick={() => setConfirm(true)} data-testid="import-publish"><Rocket size={15} />Publish as new version</button></div>}
              {active.state === "published" && <Alert tone="ok"><CheckCircle2 size={14} /> Published. Enquiries processed against the previous version must be re-run before approval.</Alert>}
              {publish.error && <Alert tone="danger">{errorMessage(publish.error)}</Alert>}
            </>
          )}
        </section>
      )}
      <section className="app-section">
        <h2>Batches</h2>
        {list.error ? <ErrorState error={list.error} onRetry={list.reload} /> : !list.data ? <Skeleton lines={3} /> : list.data.length ? (
          <div className="app-table-wrap"><table className="app-table"><thead><tr><th>File</th><th>State</th><th>Rows</th><th>Issues</th><th>Created</th></tr></thead>
            <tbody>{list.data.map((b) => <tr key={b.id} className="clickable" onClick={async () => setActive(await ws.importPreview(b.id))}><td>{b.filename}</td><td><span className="app-badge outline">{b.state}</span></td><td>{b.rows}</td><td>{b.issues}</td><td className="app-small">{formatTime(b.created_at)}</td></tr>)}</tbody></table></div>
        ) : <EmptyState icon={<ShieldAlert size={28} />} title="No import batches yet" body="Upload a CSV or try one of the samples." />}
      </section>
      <ConfirmDialog open={confirm} title="Publish a new catalogue version?" body="The validated batch becomes the active version (compare-and-set against the version it was validated on). Drafts built on the old version will need a new run before approval." confirmLabel="Publish" pending={publish.pending} onCancel={() => setConfirm(false)}
        onConfirm={async () => { setConfirm(false); const r = await publish.run(); if (r && active) { toast("ok", "New catalogue version published."); setActive(await ws.importPreview(active.id)); list.reload(); } }} />
    </>
  );
}
