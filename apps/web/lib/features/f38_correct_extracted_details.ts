// F38 Correct extracted details — typed client for POST /v1/staff/enquiries/{id}/corrections.
//
// Submits only the typed allowed correction fields (description/quantity/model/serial) + reason
// and the expected revision. It can never set status or a candidate/part fact — the payload has
// no field for either. The gateway forwards to the orchestrator correction endpoint.

import { api } from "@/lib/api";
import type { EnquiryView } from "@/lib/contracts";

export interface ItemCorrection {
  item_id: string;
  description?: string | null;
  quantity?: number | null;
  model_text?: string | null;
  serial_text?: string | null;
}

export interface F38Request {
  enquiry_id: string;
  expected_revision: number;
  corrections: ItemCorrection[];
  reason: string;
}

export interface F38Result {
  enquiry: EnquiryView;
}

export async function correctExtraction(request: F38Request): Promise<F38Result> {
  return api<F38Result>(`/v1/staff/enquiries/${request.enquiry_id}/corrections`, {
    method: "POST",
    body: JSON.stringify({
      expected_revision: request.expected_revision,
      corrections: request.corrections,
      reason: request.reason,
    }),
  });
}
