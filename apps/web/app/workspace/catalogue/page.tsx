"use client";

import { ArrowRightLeft, Boxes, Search, X } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState, type JSX } from "react";

import { EmptyState, ErrorState, Ident, PageHeader, Pager, PermissionDenied, Skeleton, formatTime } from "@/components/app/ui";
import { useLoad } from "@/lib/hooks";
import { useSession } from "@/lib/session";
import { ws } from "@/lib/workspace";

const LIMIT = 25;

export default function CataloguePage(): JSX.Element {
  return <Suspense fallback={<Skeleton lines={6} />}><Catalogue /></Suspense>;
}

function Catalogue(): JSX.Element {
  const { can, identity } = useSession();
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const q = params.get("q") ?? "";
  const category = params.get("category") ?? "";
  const model = params.get("model") ?? "";
  const cursor = Number(params.get("cursor") ?? 0) || 0;
  const part = params.get("part");
  const [draft, setDraft] = useState(q);
  const { data, error, loading, reload } = useLoad((signal) => ws.catalogue({ q, category, model, cursor, limit: LIMIT }, signal), [q, category, model, cursor]);
  const detail = useLoad(async () => (part ? ws.part(part) : null), [part]);
  if (!can("catalogue.browse")) return <PermissionDenied />;
  const update = (next: Record<string, string | number | null>) => {
    const merged = new URLSearchParams(params.toString());
    for (const [key, value] of Object.entries(next)) {
      if (value === "" || value === null || value === 0) merged.delete(key); else merged.set(key, String(value));
    }
    if (!("cursor" in next) && !("part" in next)) merged.delete("cursor");
    router.push(`${pathname}${merged.size ? `?${merged}` : ""}`);
  };
  return (
    <>
      <PageHeader title="Catalogue" description={<>The active published catalogue version{data?.version ? <> · <strong>{data.version.label}</strong> published {formatTime(data.version.published_at)}</> : null}. {identity?.kind === "demo" ? "Imports you publish in the demo change only your sandbox copy." : ""} All data is synthetic.</>} />
      <form className="app-filters" role="search" onSubmit={(e) => { e.preventDefault(); update({ q: draft.trim() }); }}>
        <label className="app-field"><span>Search</span><input className="app-input" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Part number, name (EN/AR) or alias" maxLength={200} /></label>
        <label className="app-field"><span>Category</span><select value={category} onChange={(e) => update({ category: e.target.value })}><option value="">All</option>{data?.categories.map((c) => <option key={c} value={c}>{c}</option>)}</select></label>
        <label className="app-field"><span>Fits model</span><select value={model} onChange={(e) => update({ model: e.target.value })}><option value="">Any</option>{data?.models.map((m) => <option key={m} value={m}>{m}</option>)}</select></label>
        <button className="app-btn" type="submit"><Search size={15} />Search</button>
      </form>
      <div className={part ? "app-split" : undefined}>
        <section>
          {error ? <ErrorState error={error} onRetry={reload} /> : loading && !data ? <Skeleton lines={6} /> : data && (data.items.length ? (
            <>
              <div className="app-table-wrap"><table className="app-table" data-testid="catalogue-table">
                <thead><tr><th>Part</th><th>Name</th><th>Category</th><th>Aliases</th></tr></thead>
                <tbody>{data.items.map((p) => (
                  <tr key={p.id} className="clickable" onClick={() => update({ part: p.part_number })} aria-selected={part === p.part_number}>
                    <td><button className="app-btn ghost small" onClick={(e) => { e.stopPropagation(); update({ part: p.part_number }); }}><Ident>{p.part_number}</Ident></button>{!p.is_active && <span className="app-badge">inactive</span>}</td>
                    <td>{p.name_en}<div className="app-small app-muted" dir="rtl">{p.name_ar}</div></td>
                    <td className="app-small">{p.category}</td>
                    <td className="app-small app-muted">{p.aliases.join(", ") || "—"}</td>
                  </tr>
                ))}</tbody>
              </table></div>
              <Pager cursor={cursor} total={data.total} limit={LIMIT} onChange={(next) => update({ cursor: next })} />
            </>
          ) : <EmptyState icon={<Boxes size={28} />} title="No parts match" body="Try another term or clear the filters." />)}
        </section>
        {part && (
          <aside className="app-card app-stack" data-testid="part-detail">
            <div className="app-row" style={{ justifyContent: "space-between" }}><h2 className="app-card-title" style={{ margin: 0 }}><Ident>{part}</Ident></h2><button className="app-btn ghost small" aria-label="Close detail" onClick={() => update({ part: null })}><X size={16} /></button></div>
            {detail.error ? <ErrorState error={detail.error} /> : !detail.data ? <Skeleton lines={5} /> : (
              <>
                <div>{detail.data.name_en} <span dir="rtl" className="app-muted">· {detail.data.name_ar}</span></div>
                <p className="app-small app-muted">{detail.data.description_en}</p>
                <dl className="app-kv app-small"><dt>Category</dt><dd>{detail.data.category}</dd><dt>Unit</dt><dd>{detail.data.unit_of_measure}</dd><dt>Version</dt><dd className="app-mono">{detail.data.catalogue_version_id.slice(0, 8)}</dd></dl>
                <h3 className="app-card-title">Fits (with source)</h3>
                {detail.data.compatibility.length ? <ul className="app-small" style={{ margin: 0, paddingInlineStart: 18 }}>{detail.data.compatibility.map((c, i) => <li key={i}>{c.brand} {c.model_code} config {c.config_code} × {c.quantity_per_unit} — <span className="app-mono">{c.source_reference}</span></li>)}</ul> : <p className="app-small app-muted">No fitment rows.</p>}
                {(detail.data.supersedes.length > 0 || detail.data.superseded_by.length > 0) && (
                  <><h3 className="app-card-title"><ArrowRightLeft size={14} />Supersession</h3>
                    <ul className="app-small" style={{ margin: 0, paddingInlineStart: 18 }}>
                      {detail.data.supersedes.map((s) => <li key={s.old}>Replaces <Ident>{s.old}</Ident> ({s.effective_date}{s.reason ? `, ${s.reason}` : ""})</li>)}
                      {detail.data.superseded_by.map((s) => <li key={s.new}>Replaced by <Ident>{s.new}</Ident> ({s.effective_date})</li>)}
                    </ul>
                    <p className="app-small app-muted">A successor is offered only where it has its own fitment row.</p></>
                )}
                <h3 className="app-card-title">Aliases</h3>
                <p className="app-small">{detail.data.aliases.map((a) => `${a.alias} (${a.language})`).join(", ") || "—"}</p>
                <h3 className="app-card-title">Stock (synthetic)</h3>
                <ul className="app-small" style={{ margin: 0, paddingInlineStart: 18 }}>{detail.data.stock.map((s) => <li key={s.warehouse_code}>{s.warehouse_name}: {s.available}</li>)}</ul>
              </>
            )}
          </aside>
        )}
      </div>
    </>
  );
}
