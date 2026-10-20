"use client";

import { CheckCircle2, Download, FileUp, Rocket, ShieldAlert } from "lucide-react";
import { useCallback, useRef, useState, type JSX } from "react";

import { Alert, ConfirmDialog, EmptyState, ErrorState, Ident, PageHeader, PermissionDenied, Skeleton, useDates, useToast } from "@/components/app/ui";
import { useLabel, useT, useTx } from "@/lib/app-i18n";
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
  const t = useT();
  const tx = useTx();
  const label = useLabel();
  const { time } = useDates();
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
      <PageHeader title={t("imp.title")} description={<>{t("imp.desc")}{identity?.kind === "demo" ? t("imp.descDemo") : ""}</>} />
      <div className="app-row" style={{ marginBottom: 14 }}>
        <input ref={fileRef} type="file" accept=".csv,text/csv" hidden onChange={async (e) => { const f = e.target.files?.[0]; if (f) await run(f.name, await f.text()); e.target.value = ""; }} />
        <button className="app-btn primary" disabled={busy} onClick={() => fileRef.current?.click()}><FileUp size={15} />{t("imp.upload")}</button>
        <button className="app-btn" disabled={busy} onClick={() => run("valid-sample.csv", TEMPLATE)} data-testid="import-valid">{t("imp.tryValid")}</button>
        <button className="app-btn" disabled={busy} onClick={() => run("invalid-sample.csv", INVALID_SAMPLE)} data-testid="import-invalid">{t("imp.tryInvalid")}</button>
        <a className="app-btn ghost" href={`data:text/csv;charset=utf-8,${encodeURIComponent(TEMPLATE)}`} download="partsiq-import-template.csv"><Download size={15} />{t("imp.template")}</a>
      </div>
      {busy && <Skeleton lines={3} />}
      {err !== null && <ErrorState error={err} />}
      {active && (
        <section className="app-card app-stack" data-testid="import-report" data-state={active.state}>
          <h2 className="app-card-title"><bdi>{active.filename}</bdi><span className={`app-badge ${active.state === "validated" ? "ok" : active.state === "published" ? "accent" : "danger"}`}>{label("importState", active.state)}</span></h2>
          <p className="app-small app-muted">{tx("imp.summary", { rows: active.row_count, sha: <Ident>{active.content_sha256?.slice(0, 12)}</Ident>, base: <Ident>{active.base_version_id?.slice(0, 8)}</Ident> })}{!active.base_is_active && t("imp.notActive")}</p>
          {blocking.length ? (
            <>
              <Alert tone="danger" title={t("imp.blocking", { n: blocking.length })} />
              <div className="app-table-wrap"><table className="app-table" data-testid="import-issues"><thead><tr><th>{t("imp.thRow")}</th><th>{t("imp.thField")}</th><th>{t("imp.thCode")}</th><th>{t("imp.thMessage")}</th></tr></thead>
                <tbody>{active.issues.map((i, n) => <tr key={n}><td>{i.row_number || "—"}</td><td><Ident>{i.field}</Ident></td><td><bdi className="app-badge danger">{i.code}</bdi></td><td className="app-small" dir="auto">{i.message}</td></tr>)}</tbody></table></div>
            </>
          ) : (
            <>
              <Alert tone="ok" title={t("imp.passedTitle")}>{t("imp.passedBody")}</Alert>
              <dl className="app-kv app-small">
                <dt>{t("imp.added")}</dt><dd dir="ltr">{Object.entries(active.preview.added ?? {}).map(([k, v]) => `${v} ${k}`).join(", ") || "—"}</dd>
                <dt>{t("imp.changed")}</dt><dd dir="ltr">{Object.entries(active.preview.changed ?? {}).map(([k, v]) => `${v} ${k}`).join(", ") || "—"}</dd>
              </dl>
              {active.preview.samples && <ul className="app-small" style={{ margin: 0, paddingInlineStart: 18 }}>{active.preview.samples.map((s) => <li key={s.row_number}>{tx("imp.sampleRow", { n: s.row_number, action: <bdi className="app-mono">{s.action}</bdi>, entity: <bdi className="app-mono">{s.entity_type}</bdi>, summary: <bdi dir="auto">{s.summary}</bdi> })}</li>)}</ul>}
              {active.state === "validated" && <div><button className="app-btn primary" disabled={!can("catalogue.publish") || publish.pending} onClick={() => setConfirm(true)} data-testid="import-publish"><Rocket size={15} />{t("imp.publish")}</button></div>}
              {active.state === "published" && <Alert tone="ok"><CheckCircle2 size={14} /> {t("imp.publishedNote")}</Alert>}
              {publish.error && <Alert tone="danger">{errorMessage(publish.error)}</Alert>}
            </>
          )}
        </section>
      )}
      <section className="app-section">
        <h2>{t("imp.batches")}</h2>
        {list.error ? <ErrorState error={list.error} onRetry={list.reload} /> : !list.data ? <Skeleton lines={3} /> : list.data.length ? (
          <div className="app-table-wrap"><table className="app-table"><thead><tr><th>{t("imp.thFile")}</th><th>{t("imp.thState")}</th><th>{t("imp.thRows")}</th><th>{t("imp.thIssues")}</th><th>{t("common.created")}</th></tr></thead>
            <tbody>{list.data.map((b) => <tr key={b.id} className="clickable" onClick={async () => setActive(await ws.importPreview(b.id))}><td><bdi>{b.filename}</bdi></td><td><span className="app-badge outline">{label("importState", b.state)}</span></td><td>{b.rows}</td><td>{b.issues}</td><td className="app-small">{time(b.created_at)}</td></tr>)}</tbody></table></div>
        ) : <EmptyState icon={<ShieldAlert size={28} />} title={t("imp.empty")} body={t("imp.emptyBody")} />}
      </section>
      <ConfirmDialog open={confirm} title={t("imp.confirmTitle")} body={t("imp.confirmBody")} confirmLabel={t("imp.confirmLabel")} pending={publish.pending} onCancel={() => setConfirm(false)}
        onConfirm={async () => { setConfirm(false); const r = await publish.run(); if (r && active) { toast("ok", t("imp.publishedToast")); setActive(await ws.importPreview(active.id)); list.reload(); } }} />
    </>
  );
}
