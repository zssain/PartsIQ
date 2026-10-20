"use client";

import { ArrowRight, Bot, ClipboardCheck, MessageSquareWarning, PlusCircle, Workflow } from "lucide-react";
import Link from "next/link";
import type { JSX } from "react";

import { EnquiryTable } from "@/components/app/EnquiryTable";
import { Alert, EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/app/ui";
import { useT } from "@/lib/app-i18n";
import { useLoad } from "@/lib/hooks";
import { useSections, useSession } from "@/lib/session";
import { ws } from "@/lib/workspace";

export default function DashboardPage(): JSX.Element {
  const { identity, can } = useSession();
  const { demo, showReview, showAdmin } = useSections();
  const { data, error, loading, reload } = useLoad((signal) => ws.dashboard(signal));
  const status = useLoad(() => ws.status());
  const t = useT();

  const name = identity?.display_name ?? identity?.email;
  const title = identity?.kind === "demo" ? t("dash.welcomeDemo") : name ? t("dash.welcome", { name }) : t("dash.welcomeAnon");
  return (
    <>
      <PageHeader
        title={title}
        description={demo ? t("dash.descDemo") : t("dash.descAccount")}
        actions={can("enquiry.create") ? <Link className="app-btn primary" href="/workspace/enquiries/new"><PlusCircle size={16} />{t("nav.new")}</Link> : undefined}
      />
      {status.data && !status.data.live_available && (
        <Alert tone="info" title={t("dash.fixtureTitle")}>
          {t("dash.fixtureBody")}{status.data.live_unavailable_reason ? <> — <span dir="auto">{String(status.data.live_unavailable_reason)}</span></> : ""}.
        </Alert>
      )}
      {error ? <ErrorState error={error} onRetry={reload} /> : loading && !data ? <Skeleton lines={4} /> : data && (
        <>
          <section className="app-section">
            <div className="app-grid cols-4">
              <Stat id="your-enquiries" label={t("dash.statEnquiries")} value={data.total} href="/workspace/enquiries" />
              <Stat id="need-your-input" label={t("dash.statNeedInput")} value={data.counts.needs_information ?? 0} href="/workspace/enquiries?status=needs_information" tone="warn" />
              <Stat id="in-human-review" label={t("dash.statInReview")} value={data.counts.awaiting_review ?? 0} href="/workspace/enquiries?status=awaiting_review" />
              <Stat id="answered" label={t("dash.statAnswered")} value={data.counts.approved ?? 0} href="/workspace/enquiries?status=approved" />
            </div>
          </section>
          {data.needs_you.length > 0 && (
            <section className="app-section">
              <h2><MessageSquareWarning size={16} /> {t("dash.waiting")}</h2>
              <div className="app-card app-list">
                {data.needs_you.map((item) => (
                  <Link key={item.id} href={`/workspace/enquiries/${item.id}`} className="app-row" style={{ textDecoration: "none", justifyContent: "space-between" }}>
                    <span dir="auto">{item.question}</span><ArrowRight size={16} className="app-flip-rtl" />
                  </Link>
                ))}
              </div>
            </section>
          )}
          {showReview && data.review && (
            <section className="app-section">
              <h2><ClipboardCheck size={16} /> {t("dash.reviewWork")}</h2>
              <div className="app-grid cols-4">
                <Stat id="awaiting-review" label={t("dash.awaitingReview")} value={data.review.awaiting_review} href="/workspace/review?status=awaiting_review" />
                <Stat id="assigned-to-you" label={t("dash.assignedToYou")} value={data.review.assigned_to_me} href="/workspace/review?assigned=me" />
                <Stat id="exceptions" label={t("dash.exceptions")} value={data.review.exceptions} href="/workspace/review?status=failed" tone="danger" />
                <Stat id="overdue" label={t("dash.overdue")} value={data.review.overdue} href="/workspace/review?overdue=1" tone="warn" />
              </div>
            </section>
          )}
          <section className="app-section">
            <h2>{t("dash.recent")}</h2>
            {data.recent.length ? <EnquiryTable rows={data.recent} /> : (
              <EmptyState
                title={t("dash.noEnquiries")}
                body={t("dash.noEnquiriesBody")}
                action={can("enquiry.create") ? <Link className="app-btn primary" href="/workspace/enquiries/new"><PlusCircle size={16} />{t("dash.start")}</Link> : undefined}
              />
            )}
          </section>
          <section className="app-section">
            <div className="app-grid cols-2">
              <div className="app-card">
                <h3 className="app-card-title"><Workflow size={16} /> {t("mode.guided")}</h3>
                <p className="app-muted">{t("dash.guidedBody")}</p>
              </div>
              <div className="app-card">
                <h3 className="app-card-title"><Bot size={16} /> {t("mode.collaboration")}</h3>
                <p className="app-muted">{t("dash.collabBody")}</p>
              </div>
            </div>
          </section>
          {showAdmin && <p className="app-small app-muted" style={{ marginTop: 16 }}>{demo ? t("dash.adminScopeDemo") : t("dash.adminScopeAccount")}</p>}
        </>
      )}
    </>
  );
}

// `id` keeps the test id stable (it used to be derived from the English label).
function Stat({ id, label, value, href, tone }: { id: string; label: string; value: number; href: string; tone?: "warn" | "danger" }): JSX.Element {
  return (
    <Link href={href} className="app-card app-stat" style={{ textDecoration: "none" }} data-testid={`stat-${id}`}>
      <strong style={{ color: tone === "warn" && value ? "var(--app-warn)" : tone === "danger" && value ? "var(--app-danger)" : undefined }}>{value}</strong>
      <span>{label}</span>
    </Link>
  );
}
