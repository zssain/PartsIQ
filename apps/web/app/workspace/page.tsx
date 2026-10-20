"use client";

import { ArrowRight, Bot, ClipboardCheck, MessageSquareWarning, PlusCircle, Workflow } from "lucide-react";
import Link from "next/link";
import type { JSX } from "react";

import { EnquiryTable } from "@/components/app/EnquiryTable";
import { Alert, EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/app/ui";
import { useLoad } from "@/lib/hooks";
import { useSections, useSession } from "@/lib/session";
import { ws } from "@/lib/workspace";

export default function DashboardPage(): JSX.Element {
  const { identity, can } = useSession();
  const { demo, showReview, showAdmin } = useSections();
  const { data, error, loading, reload } = useLoad((signal) => ws.dashboard(signal));
  const status = useLoad(() => ws.status());

  const name = identity?.kind === "demo" ? "demo visitor" : identity?.display_name ?? identity?.email ?? "there";
  return (
    <>
      <PageHeader
        title={`Welcome, ${name}`}
        description={demo
          ? "This is your private demo workspace. Everything you create here is synthetic and disposable. Use “Preview as” to switch between the customer, reviewer and administrator experience."
          : "Your enquiries, review work and administration in one place."}
        actions={can("enquiry.create") ? <Link className="app-btn primary" href="/workspace/enquiries/new"><PlusCircle size={16} />New enquiry</Link> : undefined}
      />
      {status.data && !status.data.live_available && (
        <Alert tone="info" title="Execution mode: fixture replay">
          Runs use deterministic fixture specialists and the real compatibility, fulfilment and verification services over the synthetic catalogue. No live model calls are made{status.data.live_unavailable_reason ? ` — ${String(status.data.live_unavailable_reason)}` : ""}.
        </Alert>
      )}
      {error ? <ErrorState error={error} onRetry={reload} /> : loading && !data ? <Skeleton lines={4} /> : data && (
        <>
          <section className="app-section">
            <div className="app-grid cols-4">
              <Stat label="Your enquiries" value={data.total} href="/workspace/enquiries" />
              <Stat label="Need your input" value={data.counts.needs_information ?? 0} href="/workspace/enquiries?status=needs_information" tone="warn" />
              <Stat label="In human review" value={data.counts.awaiting_review ?? 0} href="/workspace/enquiries?status=awaiting_review" />
              <Stat label="Answered" value={data.counts.approved ?? 0} href="/workspace/enquiries?status=approved" />
            </div>
          </section>
          {data.needs_you.length > 0 && (
            <section className="app-section">
              <h2><MessageSquareWarning size={16} /> Waiting for your answer</h2>
              <div className="app-card app-list">
                {data.needs_you.map((item) => (
                  <Link key={item.id} href={`/workspace/enquiries/${item.id}`} className="app-row" style={{ textDecoration: "none", justifyContent: "space-between" }}>
                    <span>{item.question}</span><ArrowRight size={16} />
                  </Link>
                ))}
              </div>
            </section>
          )}
          {showReview && data.review && (
            <section className="app-section">
              <h2><ClipboardCheck size={16} /> Review work</h2>
              <div className="app-grid cols-4">
                <Stat label="Awaiting review" value={data.review.awaiting_review} href="/workspace/review?status=awaiting_review" />
                <Stat label="Assigned to you" value={data.review.assigned_to_me} href="/workspace/review?assigned=me" />
                <Stat label="Exceptions" value={data.review.exceptions} href="/workspace/review?status=failed" tone="danger" />
                <Stat label="Overdue" value={data.review.overdue} href="/workspace/review?overdue=1" tone="warn" />
              </div>
            </section>
          )}
          <section className="app-section">
            <h2>Recent enquiries</h2>
            {data.recent.length ? <EnquiryTable rows={data.recent} /> : (
              <EmptyState
                title="No enquiries yet"
                body="Describe a part in English, Arabic or both. The system identifies the machine, checks compatibility and stock, and a human approves the reply."
                action={can("enquiry.create") ? <Link className="app-btn primary" href="/workspace/enquiries/new"><PlusCircle size={16} />Start an enquiry</Link> : undefined}
              />
            )}
          </section>
          <section className="app-section">
            <div className="app-grid cols-2">
              <div className="app-card">
                <h3 className="app-card-title"><Workflow size={16} /> Guided workflow</h3>
                <p className="app-muted">Code moves the enquiry through intake, identification, compatible search, stock planning, drafting and verification, then waits for a person.</p>
              </div>
              <div className="app-card">
                <h3 className="app-card-title"><Bot size={16} /> Agent collaboration</h3>
                <p className="app-muted">Intake, Nameplate, Parts and Reply specialists exchange addressed requests and evidence. A controller enforces who may talk to whom, which tools they may call and when you must consent.</p>
              </div>
            </div>
          </section>
          {showAdmin && <p className="app-small app-muted" style={{ marginTop: 16 }}>Administration screens act on {demo ? "this demo session's disposable sandbox only" : "the invited-account workspace"}.</p>}
        </>
      )}
    </>
  );
}

function Stat({ label, value, href, tone }: { label: string; value: number; href: string; tone?: "warn" | "danger" }): JSX.Element {
  return (
    <Link href={href} className="app-card app-stat" style={{ textDecoration: "none" }} data-testid={`stat-${label.toLowerCase().replace(/\s+/g, "-")}`}>
      <strong style={{ color: tone === "warn" && value ? "var(--app-warn)" : tone === "danger" && value ? "var(--app-danger)" : undefined }}>{value}</strong>
      <span>{label}</span>
    </Link>
  );
}
