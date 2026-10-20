"use client";

import { Search } from "lucide-react";
import { useState, type JSX } from "react";

import { EmptyState, ErrorState, PageHeader, Pager, PermissionDenied, Skeleton, formatTime } from "@/components/app/ui";
import { useLoad } from "@/lib/hooks";
import { useSession } from "@/lib/session";
import { ws } from "@/lib/workspace";

const LIMIT = 50;

export default function AuditPage(): JSX.Element {
  const { can } = useSession();
  const [filters, setFilters] = useState({ action: "", entity: "" });
  const [draft, setDraft] = useState(filters);
  const [cursor, setCursor] = useState(0);
  const { data, error, loading, reload } = useLoad(() => ws.audit({ ...filters, cursor, limit: LIMIT }), [filters, cursor]);
  if (!can("audit.read")) return <PermissionDenied />;
  return (
    <>
      <PageHeader title="Audit trail" description="Append-only record of decisions, run commands, assignments, imports and role changes. Read-only: there is no edit or delete." />
      <form className="app-filters" onSubmit={(e) => { e.preventDefault(); setCursor(0); setFilters(draft); }}>
        <label className="app-field"><span>Action</span><input className="app-input" value={draft.action} onChange={(e) => setDraft({ ...draft, action: e.target.value })} placeholder="e.g. review.approved" /></label>
        <label className="app-field"><span>Resource</span><input className="app-input" value={draft.entity} onChange={(e) => setDraft({ ...draft, entity: e.target.value })} placeholder="enquiry, run, member, id…" /></label>
        <button className="app-btn" type="submit"><Search size={15} />Filter</button>
      </form>
      {error ? <ErrorState error={error} onRetry={reload} /> : loading && !data ? <Skeleton lines={6} /> : data && (data.items.length ? (
        <>
          <div className="app-table-wrap"><table className="app-table" data-testid="audit-table">
            <thead><tr><th>#</th><th>When</th><th>Actor</th><th>Action</th><th>Resource</th><th>Revision</th><th>Details</th></tr></thead>
            <tbody>{data.items.map((a) => (
              <tr key={a.seq}>
                <td className="app-mono">{a.seq}</td><td className="app-small">{formatTime(a.created_at)}</td>
                <td className="app-small">{a.actor_label}<div className="app-muted">{a.actor_type}</div></td>
                <td><span className="app-badge outline app-mono">{a.action}</span></td>
                <td className="app-small">{a.entity_type} <span className="app-mono app-muted">{a.entity_id.slice(0, 8)}</span></td>
                <td>{a.revision ?? "—"}</td>
                <td className="app-small app-muted app-mono">{Object.entries(a.payload).map(([k, v]) => `${k}=${String(v)}`).join(" ") || "—"}</td>
              </tr>
            ))}</tbody>
          </table></div>
          <Pager cursor={cursor} total={data.total} limit={LIMIT} onChange={setCursor} />
        </>
      ) : <EmptyState title="No audit events match" />)}
    </>
  );
}
