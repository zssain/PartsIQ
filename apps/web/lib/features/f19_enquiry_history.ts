// F19 Enquiry history — typed client for GET /v1/enquiries (owner gateway).
//
// Ownership is enforced server-side from the verified token; the browser never sends an owner
// id. Only typed identifiers (cursor/limit/status) are submitted.

import { api } from "@/lib/api";
import type { EnquiryView } from "@/lib/contracts";

export interface F19Request {
  cursor?: string | null;
  limit?: number;
  status?: string | null;
}

export interface F19Result {
  enquiries: EnquiryView[];
  next_cursor: string | null;
}

export async function listHistory(request: F19Request = {}): Promise<F19Result> {
  const params = new URLSearchParams();
  if (request.cursor) params.set("cursor", request.cursor);
  if (request.limit) params.set("limit", String(request.limit));
  if (request.status) params.set("status", request.status);
  const query = params.toString();
  return api<F19Result>(`/v1/enquiries${query ? `?${query}` : ""}`);
}
