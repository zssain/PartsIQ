"use client";

import { Search } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState, type JSX } from "react";

import { EnquiryTable } from "@/components/app/EnquiryTable";
import { EmptyState, ErrorState, PageHeader, Pager, PermissionDenied, Skeleton } from "@/components/app/ui";
import { useT, type TKey } from "@/lib/app-i18n";
import { useLoad } from "@/lib/hooks";
import { useSession } from "@/lib/session";
import { ws } from "@/lib/workspace";

const LIMIT = 20;
const QUEUES: [string, TKey][] = [
  ["awaiting_review", "queue.tab.awaiting_review"], ["needs_information", "queue.tab.needs_information"], ["failed", "queue.tab.failed"],
  ["processing", "queue.tab.processing"], ["approved", "queue.tab.approved"], ["rejected", "queue.tab.rejected"], ["", "common.all"],
];

export default function ReviewQueuePage(): JSX.Element {
  return <Suspense fallback={<Skeleton lines={6} />}><Queue /></Suspense>;
}

function Queue(): JSX.Element {
  const { can, identity } = useSession();
  const t = useT();
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const status = params.get("status") ?? "awaiting_review";
  const assigned = params.get("assigned") ?? "";
  const overdue = params.get("overdue") === "1";
  const q = params.get("q") ?? "";
  const cursor = Number(params.get("cursor") ?? 0) || 0;
  const [draft, setDraft] = useState(q);
  const { data, error, loading, reload } = useLoad((signal) => ws.enquiries({ scope: "review", status, assigned, overdue: overdue ? "true" : undefined, q, cursor, limit: LIMIT }, signal), [status, assigned, overdue, q, cursor]);
  if (!can("review.queue")) return <PermissionDenied />;
  const update = (next: Record<string, string | number>) => {
    const merged = new URLSearchParams(params.toString());
    for (const [key, value] of Object.entries(next)) {
      if (value === "" && key !== "status") merged.delete(key);
      else merged.set(key, String(value));
    }
    if (!("cursor" in next)) merged.delete("cursor");
    router.push(`${pathname}?${merged}`);
  };
  const scopeNote = identity?.kind === "demo"
    ? t("queue.scopeDemo")
    : identity?.roles.includes("admin") ? t("queue.scopeAdmin") : t("queue.scopeReviewer");
  return (
    <>
      <PageHeader title={t("nav.review")} description={scopeNote} />
      <div className="app-seg" role="group" aria-label={t("queue.aria")} style={{ marginBottom: 12 }}>
        {QUEUES.map(([value, label]) => <button key={value || "all"} type="button" aria-pressed={status === value} onClick={() => update({ status: value })}>{t(label)}</button>)}
      </div>
      <form className="app-filters" role="search" onSubmit={(e) => { e.preventDefault(); update({ q: draft.trim() }); }}>
        <label className="app-field"><span>{t("common.search")}</span><input className="app-input" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder={t("queue.searchPlaceholder")} dir="auto" maxLength={200} /></label>
        <label className="app-field"><span>{t("queue.assignment")}</span>
          <select value={assigned} onChange={(e) => update({ assigned: e.target.value })}><option value="">{t("queue.anyone")}</option><option value="me">{t("queue.assignedToMe")}</option><option value="none">{t("common.unassigned")}</option></select>
        </label>
        <label className="app-row app-small" style={{ alignSelf: "center" }}><input type="checkbox" checked={overdue} onChange={(e) => update({ overdue: e.target.checked ? "1" : "" })} />{t("queue.overdueOnly")}</label>
        <button className="app-btn" type="submit"><Search size={15} />{t("common.search")}</button>
      </form>
      {error ? <ErrorState error={error} onRetry={reload} /> : loading && !data ? <Skeleton lines={6} /> : data && (data.items.length ? (
        <>
          <EnquiryTable rows={data.items} review />
          <Pager cursor={cursor} total={data.total} limit={LIMIT} onChange={(next) => update({ cursor: next })} />
        </>
      ) : <EmptyState title={t("queue.empty")} body={t("queue.emptyBody")} />)}
    </>
  );
}
