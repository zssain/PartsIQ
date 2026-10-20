"use client";

import { Search } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState, type JSX } from "react";

import { EnquiryTable } from "@/components/app/EnquiryTable";
import { EmptyState, ErrorState, PageHeader, Pager, PermissionDenied, Skeleton } from "@/components/app/ui";
import { useLoad } from "@/lib/hooks";
import { useSession } from "@/lib/session";
import { ws } from "@/lib/workspace";

const LIMIT = 20;
const QUEUES: [string, string][] = [
  ["awaiting_review", "Awaiting review"], ["needs_information", "Waiting for customer"], ["failed", "Exceptions"],
  ["processing", "Processing"], ["approved", "Approved"], ["rejected", "Rejected"], ["", "All"],
];

export default function ReviewQueuePage(): JSX.Element {
  return <Suspense fallback={<Skeleton lines={6} />}><Queue /></Suspense>;
}

function Queue(): JSX.Element {
  const { can, identity } = useSession();
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
    ? "Demo sandbox: every enquiry in your session is reviewable by you. With real accounts, reviewers see only enquiries assigned to them; administrators see all."
    : identity?.roles.includes("admin") ? "You see every enquiry in the workspace." : "You see enquiries assigned to you.";
  return (
    <>
      <PageHeader title="Review queue" description={scopeNote} />
      <div className="app-seg" role="group" aria-label="Queue" style={{ marginBottom: 12 }}>
        {QUEUES.map(([value, label]) => <button key={value || "all"} type="button" aria-pressed={status === value} onClick={() => update({ status: value })}>{label}</button>)}
      </div>
      <form className="app-filters" role="search" onSubmit={(e) => { e.preventDefault(); update({ q: draft.trim() }); }}>
        <label className="app-field"><span>Search</span><input className="app-input" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Text, part or id" maxLength={200} /></label>
        <label className="app-field"><span>Assignment</span>
          <select value={assigned} onChange={(e) => update({ assigned: e.target.value })}><option value="">Anyone</option><option value="me">Assigned to me</option><option value="none">Unassigned</option></select>
        </label>
        <label className="app-row app-small" style={{ alignSelf: "center" }}><input type="checkbox" checked={overdue} onChange={(e) => update({ overdue: e.target.checked ? "1" : "" })} />Overdue only</label>
        <button className="app-btn" type="submit"><Search size={15} />Search</button>
      </form>
      {error ? <ErrorState error={error} onRetry={reload} /> : loading && !data ? <Skeleton lines={6} /> : data && (data.items.length ? (
        <>
          <EnquiryTable rows={data.items} review />
          <Pager cursor={cursor} total={data.total} limit={LIMIT} onChange={(next) => update({ cursor: next })} />
        </>
      ) : <EmptyState title="Nothing in this queue" body="When an enquiry needs a decision it appears here." />)}
    </>
  );
}
