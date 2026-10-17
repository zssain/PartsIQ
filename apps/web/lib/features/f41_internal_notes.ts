// F41 Internal notes — typed client for the staff notes routes (owner gateway).
//
// Staff-only. Notes never appear in a customer response or the PDF. Submits only the typed
// note body + enquiry id + idempotency key.

import { api } from "@/lib/api";

export interface F41Request {
  enquiry_id: string;
  body: string;
  idempotency_key: string;
}

export interface F41Result {
  id: string;
  author_id: string;
  body: string;
  created_at: string;
}

export async function appendNote(request: F41Request): Promise<F41Result> {
  return api<F41Result>(`/v1/staff/enquiries/${request.enquiry_id}/notes`, {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export async function listNotes(enquiryId: string): Promise<F41Result[]> {
  return api<F41Result[]>(`/v1/staff/enquiries/${enquiryId}/notes`);
}
