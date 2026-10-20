"use client";

import { MailPlus, Users } from "lucide-react";
import { useCallback, useState, type JSX } from "react";

import { Alert, EmptyState, ErrorState, PageHeader, PermissionDenied, Skeleton, useDates, useToast } from "@/components/app/ui";
import { useLabel, useT } from "@/lib/app-i18n";
import { errorMessage, useIdempotentAction, useLoad } from "@/lib/hooks";
import { useSession } from "@/lib/session";
import { ws, type Member } from "@/lib/workspace";

const ROLES = ["reviewer", "catalogue_admin", "admin"] as const;

export default function UsersPage(): JSX.Element {
  const { can } = useSession();
  const toast = useToast();
  const t = useT();
  const label = useLabel();
  const { data, error, loading, reload } = useLoad(() => ws.members());
  const [invite, setInvite] = useState({ email: "", display_name: "", roles: ["reviewer"] as string[] });
  const inviteFn = useCallback(async (key: string) => ws.invite({ email: invite.email.trim(), display_name: invite.display_name.trim() || undefined, roles: invite.roles }, key), [invite]);
  const inviteAction = useIdempotentAction(inviteFn);
  if (!can("admin.users")) return <PermissionDenied />;
  return (
    <>
      <PageHeader title={t("nav.users")} description={t("users.desc")} />
      {data?.note && <Alert tone={data.source === "unavailable" ? "warn" : "info"}><span dir="auto">{data.note}</span></Alert>}
      <div className="app-split" style={{ marginTop: 12 }}>
        <section>
          {error ? <ErrorState error={error} onRetry={reload} /> : loading && !data ? <Skeleton lines={5} /> : data && (data.items.length ? (
            <div className="app-table-wrap"><table className="app-table" data-testid="members-table">
              <thead><tr><th>{t("users.thMember")}</th><th>{t("acct.roles")}</th><th>{t("common.status")}</th></tr></thead>
              <tbody>{data.items.map((m) => <MemberRow key={m.id} m={m} onChanged={reload} />)}</tbody>
            </table></div>
          ) : <EmptyState icon={<Users size={28} />} title={t("users.empty")} />)}
        </section>
        <form className="app-card app-stack" onSubmit={async (e) => { e.preventDefault(); const r = await inviteAction.run(); if (r) { toast("ok", data?.source === "supabase" ? t("users.inviteSentSupabase") : t("users.inviteSandbox")); setInvite({ email: "", display_name: "", roles: ["reviewer"] }); reload(); } }}>
          <h2 className="app-card-title"><MailPlus size={16} />{t("users.invite")}</h2>
          <label className="app-field"><span>{t("common.email")}</span><input className="app-input" type="email" required value={invite.email} onChange={(e) => setInvite({ ...invite, email: e.target.value })} maxLength={254} dir="ltr" /></label>
          <label className="app-field"><span>{t("users.displayName")}</span><input className="app-input" value={invite.display_name} onChange={(e) => setInvite({ ...invite, display_name: e.target.value })} maxLength={120} dir="auto" /></label>
          <fieldset className="app-row" style={{ border: 0, padding: 0 }}><legend className="app-label">{t("acct.roles")}</legend>
            {ROLES.map((r) => <label key={r} className="app-row app-small"><input type="checkbox" checked={invite.roles.includes(r)} onChange={(e) => setInvite({ ...invite, roles: e.target.checked ? [...invite.roles, r] : invite.roles.filter((x) => x !== r) })} />{label("role", r)}</label>)}
          </fieldset>
          <small className="app-muted">{data?.source === "supabase" ? t("users.noteSupabase") : t("users.noteSandbox")}</small>
          {inviteAction.error && <Alert tone="danger">{errorMessage(inviteAction.error)}</Alert>}
          <button className="app-btn primary" disabled={inviteAction.pending || data?.source === "unavailable"}>{t("users.send")}</button>
        </form>
      </div>
    </>
  );
}

function MemberRow({ m, onChanged }: { m: Member; onChanged: () => void }): JSX.Element {
  const toast = useToast();
  const t = useT();
  const label = useLabel();
  const { time } = useDates();
  const [roles, setRoles] = useState<string[]>(m.roles);
  const setFn = useCallback(async (key: string, next: string[]) => ws.setRoles(m.id, next, m.version, key), [m.id, m.version]);
  const action = useIdempotentAction(setFn);
  const dirty = roles.join() !== m.roles.join();
  return (
    <tr data-member={m.display_name}>
      <td><strong><bdi>{m.display_name}</bdi></strong>{m.is_you && <span className="app-badge accent" style={{ marginInlineStart: 6 }}>{t("users.you")}</span>}<div className="app-small app-muted">{m.email ? <bdi dir="ltr">{m.email}</bdi> : m.kind === "persona" ? t("users.persona") : ""}</div></td>
      <td>
        <div className="app-row">{ROLES.map((r) => <label key={r} className="app-row app-small"><input type="checkbox" checked={roles.includes(r)} onChange={(e) => setRoles(e.target.checked ? [...roles, r] : roles.filter((x) => x !== r))} aria-label={t("users.roleAria", { role: label("role", r), name: m.display_name })} />{label("role", r)}</label>)}</div>
        {dirty && <button className="app-btn small primary" style={{ marginTop: 6 }} disabled={action.pending} onClick={async () => { const r = await action.run(roles); if (r) { toast("ok", t("users.rolesSaved")); onChanged(); } }}>{t("users.saveRoles")}</button>}
        {action.error && <div className="app-field-error">{errorMessage(action.error)}</div>}
      </td>
      <td className="app-small">{label("memberKind", m.kind)}{m.last_sign_in_at ? t("users.lastSignIn", { time: time(m.last_sign_in_at) }) : ""}</td>
    </tr>
  );
}
