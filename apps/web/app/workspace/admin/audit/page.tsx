"use client";

import { Search } from "lucide-react";
import { useState, type JSX } from "react";

import { EmptyState, ErrorState, Ident, PageHeader, Pager, PermissionDenied, Skeleton, useDates } from "@/components/app/ui";
import { useLabel, useT } from "@/lib/app-i18n";
import { useLoad } from "@/lib/hooks";
import { useSession } from "@/lib/session";
import { ws } from "@/lib/workspace";

const LIMIT = 50;

export default function AuditPage(): JSX.Element {
  const { can } = useSession();
  const t = useT();
  const label = useLabel();
  const { time } = useDates();
  const [filters, setFilters] = useState({ action: "", entity: "" });
  const [draft, setDraft] = useState(filters);
  const [cursor, setCursor] = useState(0);
  const { data, error, loading, reload } = useLoad(() => ws.audit({ ...filters, cursor, limit: LIMIT }), [filters, cursor]);
  if (!can("audit.read")) return <PermissionDenied />;
  return (
    <>
      <PageHeader title={t("nav.audit")} description={t("audit.desc")} />
      <form className="app-filters" onSubmit={(e) => { e.preventDefault(); setCursor(0); setFilters(draft); }}>
        <label className="app-field"><span>{t("audit.action")}</span><input className="app-input" value={draft.action} onChange={(e) => setDraft({ ...draft, action: e.target.value })} placeholder={t("audit.actionPlaceholder")} dir="ltr" /></label>
        <label className="app-field"><span>{t("audit.resource")}</span><input className="app-input" value={draft.entity} onChange={(e) => setDraft({ ...draft, entity: e.target.value })} placeholder={t("audit.resourcePlaceholder")} dir="auto" /></label>
        <button className="app-btn" type="submit"><Search size={15} />{t("audit.filter")}</button>
      </form>
      {error ? <ErrorState error={error} onRetry={reload} /> : loading && !data ? <Skeleton lines={6} /> : data && (data.items.length ? (
        <>
          <div className="app-table-wrap"><table className="app-table" data-testid="audit-table">
            <thead><tr><th>#</th><th>{t("audit.when")}</th><th>{t("audit.actor")}</th><th>{t("audit.action")}</th><th>{t("audit.resource")}</th><th>{t("audit.revision")}</th><th>{t("audit.details")}</th></tr></thead>
            <tbody>{data.items.map((a) => (
              <tr key={a.seq}>
                <td className="app-mono">{a.seq}</td><td className="app-small">{time(a.created_at)}</td>
                <td className="app-small"><bdi>{a.actor_label}</bdi><div className="app-muted">{label("actorType", a.actor_type)}</div></td>
                <td><bdi className="app-badge outline app-mono">{a.action}</bdi></td>
                <td className="app-small"><bdi className="app-mono">{a.entity_type}</bdi> <Ident>{a.entity_id.slice(0, 8)}</Ident></td>
                <td>{a.revision ?? "—"}</td>
                <td className="app-small app-muted app-mono" dir="ltr">{Object.entries(a.payload).map(([k, v]) => `${k}=${String(v)}`).join(" ") || "—"}</td>
              </tr>
            ))}</tbody>
          </table></div>
          <Pager cursor={cursor} total={data.total} limit={LIMIT} onChange={setCursor} />
        </>
      ) : <EmptyState title={t("audit.empty")} />)}
    </>
  );
}
