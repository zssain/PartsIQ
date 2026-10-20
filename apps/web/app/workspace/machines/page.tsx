"use client";

import { Archive, CheckCircle2, Plus, ShieldCheck, Wrench } from "lucide-react";
import { useCallback, useState, type JSX } from "react";

import { Alert, EmptyState, ErrorState, Ident, PageHeader, PermissionDenied, Skeleton, useDates, useToast } from "@/components/app/ui";
import { useLabel, useT } from "@/lib/app-i18n";
import { errorMessage, useIdempotentAction, useLoad } from "@/lib/hooks";
import { useSession } from "@/lib/session";
import { ws } from "@/lib/workspace";

export default function MachinesPage(): JSX.Element {
  const { can } = useSession();
  const toast = useToast();
  const t = useT();
  const label = useLabel();
  const { time } = useDates();
  const { data, error, loading, reload } = useLoad(() => ws.machines());
  const [form, setForm] = useState({ label: "", model_text: "", serial_text: "" });
  const [checks, setChecks] = useState<Record<string, { state: string; configuration_label: string | null; note: string } | string>>({});
  const saveFn = useCallback(async (key: string) => ws.saveMachine(form, key), [form]);
  const save = useIdempotentAction(saveFn);
  if (!can("machines.manage_own")) return <PermissionDenied />;
  const valid = form.label.trim() && form.model_text.trim() && form.serial_text.trim();
  return (
    <>
      <PageHeader title={t("nav.machines")} description={t("machines.desc")} />
      <div className="app-split">
        <section>
          {error ? <ErrorState error={error} onRetry={reload} /> : loading && !data ? <Skeleton lines={4} /> : data && (data.items.length ? (
            <div className="app-table-wrap"><table className="app-table">
              <thead><tr><th>{t("machines.label")}</th><th>{t("machines.model")}</th><th>{t("machines.serial")}</th><th>{t("machines.check")}</th><th /></tr></thead>
              <tbody>{data.items.map((m) => {
                const check = checks[m.id];
                return (
                  <tr key={m.id}>
                    <td><strong dir="auto">{m.label}</strong><div className="app-small app-muted">{time(m.created_at)}</div></td>
                    <td><Ident>{m.model_text}</Ident></td><td><Ident>{m.serial_text}</Ident></td>
                    <td className="app-small">{check === undefined ? <button className="app-btn small" onClick={async () => { try { const r = await ws.checkMachine(m.id); setChecks((c) => ({ ...c, [m.id]: r })); } catch (e) { setChecks((c) => ({ ...c, [m.id]: errorMessage(e) })); } }}><ShieldCheck size={14} />{t("machines.recheck")}</button>
                      : typeof check === "string" ? <span className="app-field-error">{check}</span>
                      : check.state === "resolved" ? <span><CheckCircle2 size={13} color="var(--app-ok)" /> <bdi>{check.configuration_label}</bdi></span> : <span className="app-badge warn">{label("machineState", check.state)}: <span dir="auto">{check.note}</span></span>}</td>
                    <td><button className="app-btn small ghost" aria-label={t("machines.archiveAria", { label: m.label })} onClick={async () => { await ws.archiveMachine(m.id); toast("ok", t("machines.archived")); reload(); }}><Archive size={14} /></button></td>
                  </tr>
                );
              })}</tbody>
            </table></div>
          ) : <EmptyState icon={<Wrench size={28} />} title={t("machines.empty")} body={t("machines.emptyBody")} />)}
        </section>
        <form className="app-card app-stack" onSubmit={async (e) => { e.preventDefault(); if (!valid) return; const r = await save.run(); if (r) { setForm({ label: "", model_text: "", serial_text: "" }); toast("ok", t("machines.saved")); reload(); } }}>
          <h2 className="app-card-title"><Plus size={16} />{t("machines.saveTitle")}</h2>
          <label className="app-field"><span>{t("machines.label")}</span><input className="app-input" value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} maxLength={120} placeholder={t("machines.labelPlaceholder")} dir="auto" /></label>
          <label className="app-field"><span>{t("machines.model")}</span><input className="app-input" value={form.model_text} onChange={(e) => setForm({ ...form, model_text: e.target.value })} maxLength={120} placeholder="CA-110" dir="ltr" /></label>
          <label className="app-field"><span>{t("machines.serial")}</span><input className="app-input" value={form.serial_text} onChange={(e) => setForm({ ...form, serial_text: e.target.value })} maxLength={120} placeholder="812345" dir="ltr" /></label>
          {save.error && <Alert tone="danger">{errorMessage(save.error)}</Alert>}
          <button className="app-btn primary" disabled={!valid || save.pending}>{t("common.save")}</button>
        </form>
      </div>
    </>
  );
}
