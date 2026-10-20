"use client";

import { PlusCircle, Search } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState, type JSX } from "react";

import { EnquiryTable } from "@/components/app/EnquiryTable";
import { EmptyState, ErrorState, PageHeader, Pager, Skeleton } from "@/components/app/ui";
import { useT, type TKey } from "@/lib/app-i18n";
import { useLoad } from "@/lib/hooks";
import { useSession } from "@/lib/session";
import { ws } from "@/lib/workspace";

const STATUSES: [string, TKey][] = [
  ["", "enq.allStatuses"], ["processing", "status.processing"], ["needs_information", "status.needs_information"], ["awaiting_review", "status.awaiting_review"],
  ["approved", "status.approved"], ["rejected", "status.rejected"], ["failed", "status.failed"],
];
const LIMIT = 20;

export default function EnquiriesPage(): JSX.Element {
  return <Suspense fallback={<Skeleton lines={5} />}><Enquiries /></Suspense>;
}

function Enquiries(): JSX.Element {
  const { can } = useSession();
  const t = useT();
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const status = params.get("status") ?? "";
  const mode = params.get("mode") ?? "";
  const q = params.get("q") ?? "";
  const cursor = Number(params.get("cursor") ?? 0) || 0;
  const [draft, setDraft] = useState(q);
  const { data, error, loading, reload } = useLoad((signal) => ws.enquiries({ scope: "own", status, mode, q, cursor, limit: LIMIT }, signal), [status, mode, q, cursor]);

  const update = (next: Record<string, string | number>) => {
    const merged = new URLSearchParams(params.toString());
    for (const [key, value] of Object.entries(next)) {
      if (value === "" || value === 0) merged.delete(key);
      else merged.set(key, String(value));
    }
    if (!("cursor" in next)) merged.delete("cursor");
    router.push(`${pathname}${merged.size ? `?${merged}` : ""}`);
  };

  return (
    <>
      <PageHeader title={t("nav.enquiries")} description={t("enq.desc")} actions={can("enquiry.create") ? <Link className="app-btn primary" href="/workspace/enquiries/new"><PlusCircle size={16} />{t("nav.new")}</Link> : undefined} />
      <form className="app-filters" role="search" onSubmit={(e) => { e.preventDefault(); update({ q: draft.trim() }); }}>
        <label className="app-field"><span>{t("common.search")}</span><input className="app-input" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder={t("enq.searchPlaceholder")} dir="auto" maxLength={200} /></label>
        <label className="app-field"><span>{t("common.status")}</span>
          <select value={status} onChange={(e) => update({ status: e.target.value })}>{STATUSES.map(([value, label]) => <option key={value} value={value}>{t(label)}</option>)}</select>
        </label>
        <label className="app-field"><span>{t("enq.mode")}</span>
          <select value={mode} onChange={(e) => update({ mode: e.target.value })}><option value="">{t("enq.allModes")}</option><option value="guided">{t("modeShort.guided")}</option><option value="collaboration">{t("modeShort.collaboration")}</option></select>
        </label>
        <button className="app-btn" type="submit"><Search size={15} />{t("common.search")}</button>
      </form>
      {error ? <ErrorState error={error} onRetry={reload} /> : loading && !data ? <Skeleton lines={5} /> : data && (data.items.length ? (
        <>
          <EnquiryTable rows={data.items} />
          <Pager cursor={cursor} total={data.total} limit={LIMIT} onChange={(next) => update({ cursor: next })} />
        </>
      ) : (
        <EmptyState title={q || status || mode ? t("enq.noMatch") : t("dash.noEnquiries")} body={q || status || mode ? t("enq.clearFilter") : t("enq.historyEmpty")} action={can("enquiry.create") ? <Link className="app-btn primary" href="/workspace/enquiries/new">{t("nav.new")}</Link> : undefined} />
      ))}
    </>
  );
}
