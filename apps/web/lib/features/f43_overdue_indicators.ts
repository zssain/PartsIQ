// F43 Overdue indicators — typed client for GET /v1/staff/enquiries/{id}/deadline (owner gateway).
//
// The server computes the UTC deadline and overdue flag; the browser only displays them.
// Thresholds are an internal triage aid, not a contractual SLA.

import { api } from "@/lib/api";

export interface F43Request {
  enquiry_id: string;
}

export interface F43Result {
  due_at: string;
  overdue: boolean;
  age_seconds: number;
}

export async function classifyDeadline(request: F43Request): Promise<F43Result> {
  return api<F43Result>(`/v1/staff/enquiries/${request.enquiry_id}/deadline`);
}
