// F36 Staff inbox — typed client for GET /v1/staff/enquiries (owner gateway).
//
// Access scope and counts are enforced server-side from the verified actor; the browser only
// sends typed filter identifiers. scoped_total is within the actor's access scope, never global.

import { api } from "@/lib/api";
import type { EnquiryView } from "@/lib/contracts";

export interface F36Request {
  cursor?: string | null;
  limit?: number;
  status?: string | null;
  priority?: string | null;
  overdue?: boolean;
  query?: string | null;
}

export interface F36Result {
  enquiries: EnquiryView[];
  next_cursor: string | null;
  scoped_total: number;
}

export async function listInbox(request: F36Request = {}): Promise<F36Result> {
  const params = new URLSearchParams();
  if (request.cursor) params.set("cursor", request.cursor);
  if (request.limit) params.set("limit", String(request.limit));
  if (request.status) params.set("status", request.status);
  if (request.priority) params.set("priority", request.priority);
  if (request.overdue) params.set("overdue", "true");
  if (request.query) params.set("query", request.query);
  const qs = params.toString();
  return api<F36Result>(`/v1/staff/enquiries${qs ? `?${qs}` : ""}`);
}
