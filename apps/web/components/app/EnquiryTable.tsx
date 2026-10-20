"use client";

import { Bot, Workflow } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { JSX } from "react";

import { useT, useTx } from "@/lib/app-i18n";
import type { EnquirySummary } from "@/lib/workspace";

import { RunStatusBadge, StatusBadge, useDates } from "./ui";

/** Enquiry list used by the dashboard, history and review queue (links to the right screen). */
export function EnquiryTable({ rows, review = false }: { rows: EnquirySummary[]; review?: boolean }): JSX.Element {
  const router = useRouter();
  const t = useT();
  const tx = useTx();
  const { time } = useDates();
  const base = review ? "/workspace/review" : "/workspace/enquiries";
  return (
    <div className="app-table-wrap">
      <table className="app-table" data-testid={review ? "review-table" : "enquiry-table"}>
        <thead>
          <tr>
            <th scope="col">{t("table.request")}</th>
            <th scope="col">{t("common.status")}</th>
            <th scope="col">{t("table.run")}</th>
            {review && <th scope="col">{t("table.assigned")}</th>}
            <th scope="col">{t("common.updated")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className="clickable" data-enquiry-id={row.id} onClick={() => router.push(`${base}/${row.id}`)}>
              <td style={{ maxWidth: 420 }}>
                <Link className="row-link" href={`${base}/${row.id}`} onClick={(e) => e.stopPropagation()}>{row.title || t("table.enquiry")}</Link>
                <div className="app-small app-muted app-row" style={{ gap: 6, marginTop: 2 }}>
                  {row.mode === "collaboration" ? <><Bot size={12} />{t("modeShort.collaboration")}</> : <><Workflow size={12} />{t("modeShort.guided")}</>}
                  <span>· {tx("common.rev", { rev: <bdi>{row.revision}</bdi> })}</span>
                  {row.priority === "urgent" && <span className="app-badge warn">{t("common.urgent")}</span>}
                  {row.overdue && <span className="app-badge danger">{t("common.overdue")}</span>}
                </div>
              </td>
              <td><StatusBadge status={row.status} /></td>
              <td>{row.run_status ? <RunStatusBadge status={row.run_status} /> : "—"}</td>
              {review && <td className="app-small">{row.assigned_label ?? <span className="app-muted">{t("common.unassigned")}</span>}</td>}
              <td className="app-small app-muted">{time(row.updated_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
