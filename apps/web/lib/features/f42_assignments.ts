// F42 Assignments — typed client for POST /v1/staff/enquiries/{id}/assignment (owner gateway).
//
// Admin-only. Submits only typed identifiers (the assignee id or null to unassign, the expected
// revision, an idempotency key) — never a compatibility fact.

import { api } from "@/lib/api";

export interface F42Request {
  enquiry_id: string;
  assigned_to: string | null;
  expected_revision: number;
  idempotency_key: string;
}

export interface F42Result {
  assigned_to: string | null;
  assigned_at: string;
}

export async function assignEnquiry(request: F42Request): Promise<F42Result> {
  return api<F42Result>(`/v1/staff/enquiries/${request.enquiry_id}/assignment`, {
    method: "POST",
    body: JSON.stringify(request),
  });
}
