"use client";

import { Archive, CheckCircle2, Plus, ShieldCheck, Wrench } from "lucide-react";
import { useCallback, useState, type JSX } from "react";

import { Alert, EmptyState, ErrorState, Ident, PageHeader, PermissionDenied, Skeleton, formatTime, useToast } from "@/components/app/ui";
import { errorMessage, useIdempotentAction, useLoad } from "@/lib/hooks";
import { useSession } from "@/lib/session";
import { ws } from "@/lib/workspace";

export default function MachinesPage(): JSX.Element {
  const { can } = useSession();
  const toast = useToast();
  const { data, error, loading, reload } = useLoad(() => ws.machines());
  const [form, setForm] = useState({ label: "", model_text: "", serial_text: "" });
  const [checks, setChecks] = useState<Record<string, { state: string; configuration_label: string | null; note: string } | string>>({});
  const saveFn = useCallback(async (key: string) => ws.saveMachine(form, key), [form]);
  const save = useIdempotentAction(saveFn);
  if (!can("machines.manage_own")) return <PermissionDenied />;
  const valid = form.label.trim() && form.model_text.trim() && form.serial_text.trim();
  return (
    <>
      <PageHeader title="Saved machines" description="Keep the model and serial of machines you order for. A saved machine is re-checked against the current catalogue whenever you use it — an old match is never trusted." />
      <div className="app-split">
        <section>
          {error ? <ErrorState error={error} onRetry={reload} /> : loading && !data ? <Skeleton lines={4} /> : data && (data.items.length ? (
            <div className="app-table-wrap"><table className="app-table">
              <thead><tr><th>Label</th><th>Model</th><th>Serial</th><th>Current check</th><th /></tr></thead>
              <tbody>{data.items.map((m) => {
                const check = checks[m.id];
                return (
                  <tr key={m.id}>
                    <td><strong>{m.label}</strong><div className="app-small app-muted">{formatTime(m.created_at)}</div></td>
                    <td><Ident>{m.model_text}</Ident></td><td><Ident>{m.serial_text}</Ident></td>
                    <td className="app-small">{check === undefined ? <button className="app-btn small" onClick={async () => { try { const r = await ws.checkMachine(m.id); setChecks((c) => ({ ...c, [m.id]: r })); } catch (e) { setChecks((c) => ({ ...c, [m.id]: errorMessage(e) })); } }}><ShieldCheck size={14} />Re-check</button>
                      : typeof check === "string" ? <span className="app-field-error">{check}</span>
                      : check.state === "resolved" ? <span><CheckCircle2 size={13} color="var(--app-ok)" /> {check.configuration_label}</span> : <span className="app-badge warn">{check.state}: {check.note}</span>}</td>
                    <td><button className="app-btn small ghost" aria-label={`Archive ${m.label}`} onClick={async () => { await ws.archiveMachine(m.id); toast("ok", "Archived."); reload(); }}><Archive size={14} /></button></td>
                  </tr>
                );
              })}</tbody>
            </table></div>
          ) : <EmptyState icon={<Wrench size={28} />} title="No saved machines" body="Save a machine to reuse its identifiers in later enquiries." />)}
        </section>
        <form className="app-card app-stack" onSubmit={async (e) => { e.preventDefault(); if (!valid) return; const r = await save.run(); if (r) { setForm({ label: "", model_text: "", serial_text: "" }); toast("ok", "Machine saved."); reload(); } }}>
          <h2 className="app-card-title"><Plus size={16} />Save a machine</h2>
          <label className="app-field"><span>Label</span><input className="app-input" value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} maxLength={120} placeholder="Site A compressor" /></label>
          <label className="app-field"><span>Model</span><input className="app-input" value={form.model_text} onChange={(e) => setForm({ ...form, model_text: e.target.value })} maxLength={120} placeholder="CA-110" /></label>
          <label className="app-field"><span>Serial</span><input className="app-input" value={form.serial_text} onChange={(e) => setForm({ ...form, serial_text: e.target.value })} maxLength={120} placeholder="812345" /></label>
          {save.error && <Alert tone="danger">{errorMessage(save.error)}</Alert>}
          <button className="app-btn primary" disabled={!valid || save.pending}>Save</button>
        </form>
      </div>
    </>
  );
}
