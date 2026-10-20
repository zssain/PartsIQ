"use client";

import { PlusCircle, Search } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState, type JSX } from "react";

import { EnquiryTable } from "@/components/app/EnquiryTable";
import { EmptyState, ErrorState, PageHeader, Pager, Skeleton } from "@/components/app/ui";
import { useLoad } from "@/lib/hooks";
import { useSession } from "@/lib/session";
import { ws } from "@/lib/workspace";

const STATUSES = [
  ["", "All statuses"], ["processing", "Processing"], ["needs_information", "Needs your input"], ["awaiting_review", "In human review"],
  ["approved", "Answered"], ["rejected", "Returned"], ["failed", "Needs staff attention"],
] as const;
const LIMIT = 20;

export default function EnquiriesPage(): JSX.Element {
  return <Suspense fallback={<Skeleton lines={5} />}><Enquiries /></Suspense>;
}

function Enquiries(): JSX.Element {
  const { can } = useSession();
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
      <PageHeader title="Enquiries" description="Every enquiry you have sent, with its current status and run." actions={can("enquiry.create") ? <Link className="app-btn primary" href="/workspace/enquiries/new"><PlusCircle size={16} />New enquiry</Link> : undefined} />
      <form className="app-filters" role="search" onSubmit={(e) => { e.preventDefault(); update({ q: draft.trim() }); }}>
        <label className="app-field"><span>Search</span><input className="app-input" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Part, model or text" maxLength={200} /></label>
        <label className="app-field"><span>Status</span>
          <select value={status} onChange={(e) => update({ status: e.target.value })}>{STATUSES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
        </label>
        <label className="app-field"><span>Mode</span>
          <select value={mode} onChange={(e) => update({ mode: e.target.value })}><option value="">All modes</option><option value="guided">Guided</option><option value="collaboration">Collaboration</option></select>
        </label>
        <button className="app-btn" type="submit"><Search size={15} />Search</button>
      </form>
      {error ? <ErrorState error={error} onRetry={reload} /> : loading && !data ? <Skeleton lines={5} /> : data && (data.items.length ? (
        <>
          <EnquiryTable rows={data.items} />
          <Pager cursor={cursor} total={data.total} limit={LIMIT} onChange={(next) => update({ cursor: next })} />
        </>
      ) : (
        <EmptyState title={q || status || mode ? "No enquiries match these filters" : "No enquiries yet"} body={q || status || mode ? "Clear a filter to see more." : "Your history appears here once you send an enquiry."} action={can("enquiry.create") ? <Link className="app-btn primary" href="/workspace/enquiries/new">New enquiry</Link> : undefined} />
      ))}
    </>
  );
}
