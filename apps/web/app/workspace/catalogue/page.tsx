"use client";

import { ArrowRightLeft, Boxes, Search, X } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState, type JSX } from "react";

import { EmptyState, ErrorState, Ident, PageHeader, Pager, PermissionDenied, Skeleton, useDates } from "@/components/app/ui";
import { useT, useTx } from "@/lib/app-i18n";
import { useLoad } from "@/lib/hooks";
import { useSession } from "@/lib/session";
import { ws } from "@/lib/workspace";

const LIMIT = 25;

export default function CataloguePage(): JSX.Element {
  return <Suspense fallback={<Skeleton lines={6} />}><Catalogue /></Suspense>;
}

function Catalogue(): JSX.Element {
  const { can, identity } = useSession();
  const t = useT();
  const tx = useTx();
  const { time } = useDates();
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
      <PageHeader title={t("nav.catalogue")} description={<>{t("cat.descActive")}{data?.version ? <> · {tx("cat.descPublished", { label: <strong><bdi>{data.version.label}</bdi></strong>, time: time(data.version.published_at) })}</> : null}. {identity?.kind === "demo" ? t("cat.descDemo") : ""} {t("cat.descSynthetic")}</>} />
      <form className="app-filters" role="search" onSubmit={(e) => { e.preventDefault(); update({ q: draft.trim() }); }}>
        <label className="app-field"><span>{t("common.search")}</span><input className="app-input" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder={t("cat.searchPlaceholder")} dir="auto" maxLength={200} /></label>
        <label className="app-field"><span>{t("cat.category")}</span><select value={category} onChange={(e) => update({ category: e.target.value })}><option value="">{t("common.all")}</option>{data?.categories.map((c) => <option key={c} value={c}>{c}</option>)}</select></label>
        <label className="app-field"><span>{t("cat.fitsModel")}</span><select value={model} onChange={(e) => update({ model: e.target.value })}><option value="">{t("common.any")}</option>{data?.models.map((m) => <option key={m} value={m}>{m}</option>)}</select></label>
        <button className="app-btn" type="submit"><Search size={15} />{t("common.search")}</button>
      </form>
      <div className={part ? "app-split" : undefined}>
        <section>
          {error ? <ErrorState error={error} onRetry={reload} /> : loading && !data ? <Skeleton lines={6} /> : data && (data.items.length ? (
            <>
              <div className="app-table-wrap"><table className="app-table" data-testid="catalogue-table">
                <thead><tr><th>{t("cat.thPart")}</th><th>{t("cat.thName")}</th><th>{t("cat.category")}</th><th>{t("cat.thAliases")}</th></tr></thead>
                <tbody>{data.items.map((p) => (
                  <tr key={p.id} className="clickable" onClick={() => update({ part: p.part_number })} aria-selected={part === p.part_number}>
                    <td><button className="app-btn ghost small" onClick={(e) => { e.stopPropagation(); update({ part: p.part_number }); }}><Ident>{p.part_number}</Ident></button>{!p.is_active && <span className="app-badge">{t("cat.inactive")}</span>}</td>
                    <td><bdi dir="ltr">{p.name_en}</bdi><div className="app-small app-muted" dir="rtl">{p.name_ar}</div></td>
                    <td className="app-small">{p.category}</td>
                    <td className="app-small app-muted" dir="auto">{p.aliases.join(", ") || "—"}</td>
                  </tr>
                ))}</tbody>
              </table></div>
              <Pager cursor={cursor} total={data.total} limit={LIMIT} onChange={(next) => update({ cursor: next })} />
            </>
          ) : <EmptyState icon={<Boxes size={28} />} title={t("cat.empty")} body={t("cat.emptyBody")} />)}
        </section>
        {part && (
          <aside className="app-card app-stack" data-testid="part-detail">
            <div className="app-row" style={{ justifyContent: "space-between" }}><h2 className="app-card-title" style={{ margin: 0 }}><Ident>{part}</Ident></h2><button className="app-btn ghost small" aria-label={t("cat.closeDetail")} onClick={() => update({ part: null })}><X size={16} /></button></div>
            {detail.error ? <ErrorState error={detail.error} /> : !detail.data ? <Skeleton lines={5} /> : (
              <>
                <div><bdi dir="ltr">{detail.data.name_en}</bdi> <span dir="rtl" className="app-muted">· {detail.data.name_ar}</span></div>
                <p className="app-small app-muted" dir="ltr">{detail.data.description_en}</p>
                <dl className="app-kv app-small"><dt>{t("cat.category")}</dt><dd><bdi>{detail.data.category}</bdi></dd><dt>{t("cat.unit")}</dt><dd><bdi>{detail.data.unit_of_measure}</bdi></dd><dt>{t("cat.version")}</dt><dd><Ident>{detail.data.catalogue_version_id.slice(0, 8)}</Ident></dd></dl>
                <h3 className="app-card-title">{t("cat.fits")}</h3>
                {detail.data.compatibility.length ? <ul className="app-small" style={{ margin: 0, paddingInlineStart: 18 }}>{detail.data.compatibility.map((c, i) => <li key={i}>{tx("cat.fitRow", { brand: <bdi>{c.brand}</bdi>, model: <Ident>{c.model_code}</Ident>, config: <Ident>{c.config_code}</Ident>, qty: c.quantity_per_unit })}<div className="app-muted"><Ident>{c.source_reference}</Ident></div></li>)}</ul> : <p className="app-small app-muted">{t("cat.noFitment")}</p>}
                {(detail.data.supersedes.length > 0 || detail.data.superseded_by.length > 0) && (
                  <><h3 className="app-card-title"><ArrowRightLeft size={14} />{t("cat.supersession")}</h3>
                    <ul className="app-small" style={{ margin: 0, paddingInlineStart: 18 }}>
                      {detail.data.supersedes.map((s) => <li key={s.old}>{s.reason
                        ? tx("cat.replacesReason", { old: <Ident>{s.old}</Ident>, date: <bdi>{s.effective_date}</bdi>, reason: <bdi dir="auto">{s.reason}</bdi> })
                        : tx("cat.replaces", { old: <Ident>{s.old}</Ident>, date: <bdi>{s.effective_date}</bdi> })}</li>)}
                      {detail.data.superseded_by.map((s) => <li key={s.new}>{tx("cat.replacedBy", { new: <Ident>{s.new}</Ident>, date: <bdi>{s.effective_date}</bdi> })}</li>)}
                    </ul>
                    <p className="app-small app-muted">{t("cat.successorNote")}</p></>
                )}
                <h3 className="app-card-title">{t("cat.thAliases")}</h3>
                <p className="app-small" dir="auto">{detail.data.aliases.map((a) => `${a.alias} (${a.language})`).join(", ") || "—"}</p>
                <h3 className="app-card-title">{t("cat.stock")}</h3>
                <ul className="app-small" style={{ margin: 0, paddingInlineStart: 18 }}>{detail.data.stock.map((s) => <li key={s.warehouse_code}><bdi>{s.warehouse_name}</bdi>: {s.available}</li>)}</ul>
              </>
            )}
          </aside>
        )}
      </div>
    </>
  );
}
