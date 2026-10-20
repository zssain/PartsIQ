"use client";

import { MailPlus, Users } from "lucide-react";
import { useCallback, useState, type JSX } from "react";

import { Alert, EmptyState, ErrorState, PageHeader, PermissionDenied, Skeleton, formatTime, useToast } from "@/components/app/ui";
import { errorMessage, useIdempotentAction, useLoad } from "@/lib/hooks";
import { useSession } from "@/lib/session";
import { ws, type Member } from "@/lib/workspace";

const ROLES = ["reviewer", "catalogue_admin", "admin"] as const;

export default function UsersPage(): JSX.Element {
  const { can } = useSession();
  const toast = useToast();
  const { data, error, loading, reload } = useLoad(() => ws.members());
  const [invite, setInvite] = useState({ email: "", display_name: "", roles: ["reviewer"] as string[] });
  const inviteFn = useCallback(async (key: string) => ws.invite({ email: invite.email.trim(), display_name: invite.display_name.trim() || undefined, roles: invite.roles }, key), [invite]);
  const inviteAction = useIdempotentAction(inviteFn);
  if (!can("admin.users")) return <PermissionDenied />;
  return (
    <>
      <PageHeader title="Users & access" description="Roles are stored server-side and checked on every request. Changes are version-checked and written to the audit trail." />
      {data?.note && <Alert tone={data.source === "unavailable" ? "warn" : "info"}>{data.note}</Alert>}
      <div className="app-split" style={{ marginTop: 12 }}>
        <section>
          {error ? <ErrorState error={error} onRetry={reload} /> : loading && !data ? <Skeleton lines={5} /> : data && (data.items.length ? (
            <div className="app-table-wrap"><table className="app-table" data-testid="members-table">
              <thead><tr><th>Member</th><th>Roles</th><th>Status</th></tr></thead>
              <tbody>{data.items.map((m) => <MemberRow key={m.id} m={m} onChanged={reload} />)}</tbody>
            </table></div>
          ) : <EmptyState icon={<Users size={28} />} title="No members listed" />)}
        </section>
        <form className="app-card app-stack" onSubmit={async (e) => { e.preventDefault(); const r = await inviteAction.run(); if (r) { toast("ok", data?.source === "supabase" ? "Invitation email sent by Supabase." : "Synthetic member added to your sandbox."); setInvite({ email: "", display_name: "", roles: ["reviewer"] }); reload(); } }}>
          <h2 className="app-card-title"><MailPlus size={16} />Invite</h2>
          <label className="app-field"><span>Email</span><input className="app-input" type="email" required value={invite.email} onChange={(e) => setInvite({ ...invite, email: e.target.value })} maxLength={254} /></label>
          <label className="app-field"><span>Display name</span><input className="app-input" value={invite.display_name} onChange={(e) => setInvite({ ...invite, display_name: e.target.value })} maxLength={120} /></label>
          <fieldset className="app-row" style={{ border: 0, padding: 0 }}><legend className="app-label">Roles</legend>
            {ROLES.map((r) => <label key={r} className="app-row app-small"><input type="checkbox" checked={invite.roles.includes(r)} onChange={(e) => setInvite({ ...invite, roles: e.target.checked ? [...invite.roles, r] : invite.roles.filter((x) => x !== r) })} />{r}</label>)}
          </fieldset>
          <small className="app-muted">{data?.source === "supabase" ? "Supabase emails a one-time password-setup link. No password is ever set or shown here." : "Demo sandbox: no email is sent and no real account is created."}</small>
          {inviteAction.error && <Alert tone="danger">{errorMessage(inviteAction.error)}</Alert>}
          <button className="app-btn primary" disabled={inviteAction.pending || data?.source === "unavailable"}>Send invite</button>
        </form>
      </div>
    </>
  );
}

function MemberRow({ m, onChanged }: { m: Member; onChanged: () => void }): JSX.Element {
  const toast = useToast();
  const [roles, setRoles] = useState<string[]>(m.roles);
  const setFn = useCallback(async (key: string, next: string[]) => ws.setRoles(m.id, next, m.version, key), [m.id, m.version]);
  const action = useIdempotentAction(setFn);
  const dirty = roles.join() !== m.roles.join();
  return (
    <tr data-member={m.display_name}>
      <td><strong>{m.display_name}</strong>{m.is_you && <span className="app-badge accent" style={{ marginInlineStart: 6 }}>you</span>}<div className="app-small app-muted">{m.email ?? (m.kind === "persona" ? "synthetic persona" : "")}</div></td>
      <td>
        <div className="app-row">{ROLES.map((r) => <label key={r} className="app-row app-small"><input type="checkbox" checked={roles.includes(r)} onChange={(e) => setRoles(e.target.checked ? [...roles, r] : roles.filter((x) => x !== r))} aria-label={`${r} for ${m.display_name}`} />{r}</label>)}</div>
        {dirty && <button className="app-btn small primary" style={{ marginTop: 6 }} disabled={action.pending} onClick={async () => { const r = await action.run(roles); if (r) { toast("ok", "Roles updated and audited."); onChanged(); } }}>Save roles</button>}
        {action.error && <div className="app-field-error">{errorMessage(action.error)}</div>}
      </td>
      <td className="app-small">{m.kind}{m.last_sign_in_at ? ` · last sign-in ${formatTime(m.last_sign_in_at)}` : ""}</td>
    </tr>
  );
}
