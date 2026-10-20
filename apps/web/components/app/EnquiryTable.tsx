"use client";

import { Bot, Workflow } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { JSX } from "react";

import type { EnquirySummary } from "@/lib/workspace";

import { RunStatusBadge, StatusBadge, formatTime } from "./ui";

/** Enquiry list used by the dashboard, history and review queue (links to the right screen). */
export function EnquiryTable({ rows, review = false }: { rows: EnquirySummary[]; review?: boolean }): JSX.Element {
  const router = useRouter();
  const base = review ? "/workspace/review" : "/workspace/enquiries";
  return (
    <div className="app-table-wrap">
      <table className="app-table" data-testid={review ? "review-table" : "enquiry-table"}>
        <thead>
          <tr>
            <th scope="col">Request</th>
            <th scope="col">Status</th>
            <th scope="col">Run</th>
            {review && <th scope="col">Assigned</th>}
            <th scope="col">Updated</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className="clickable" data-enquiry-id={row.id} onClick={() => router.push(`${base}/${row.id}`)}>
              <td style={{ maxWidth: 420 }}>
                <Link className="row-link" href={`${base}/${row.id}`} onClick={(e) => e.stopPropagation()}>{row.title || "Enquiry"}</Link>
                <div className="app-small app-muted app-row" style={{ gap: 6, marginTop: 2 }}>
                  {row.mode === "collaboration" ? <><Bot size={12} />Collaboration</> : <><Workflow size={12} />Guided</>}
                  <span>· rev {row.revision}</span>
                  {row.priority === "urgent" && <span className="app-badge warn">Urgent</span>}
                  {row.overdue && <span className="app-badge danger">Overdue</span>}
                </div>
              </td>
              <td><StatusBadge status={row.status} /></td>
              <td>{row.run_status ? <RunStatusBadge status={row.run_status} /> : "—"}</td>
              {review && <td className="app-small">{row.assigned_label ?? <span className="app-muted">Unassigned</span>}</td>}
              <td className="app-small app-muted">{formatTime(row.updated_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
