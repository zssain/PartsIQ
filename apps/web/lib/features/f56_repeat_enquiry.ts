// F56 Repeat enquiry — typed client for POST /v1/enquiries/{id}/repeat (owner gateway).
//
// Submits only typed identifiers (the source enquiry id, via the path, plus an idempotency
// key header). The new enquiry re-runs matching, stock and review from scratch; nothing is
// pre-approved and no prior allocation/draft/signed URL is carried.

import { api } from "@/lib/api";
import type { EnquiryView } from "@/lib/contracts";

export interface F56Request {
  source_enquiry_id: string;
  idempotency_key: string;
}

export interface F56Result {
  enquiry: EnquiryView;
}

export async function repeatEnquiry(request: F56Request): Promise<F56Result> {
  return api<F56Result>(`/v1/enquiries/${request.source_enquiry_id}/repeat`, {
    method: "POST",
    headers: { "idempotency-key": request.idempotency_key },
  });
}
