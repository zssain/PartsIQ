// F60 Missing-parts queue — typed client for PATCH /v1/staff/missing-parts/{id} (owner gateway).
//
// Assigned staff move a missing item through its status with a note. Submits only typed
// identifiers; resolving requires a note (also enforced server-side). Never fabricates stock.

import { api } from "@/lib/api";

export type MissingStatus = "investigating" | "resolved" | "unavailable";

export interface F60Request {
  item_id: string;
  status: MissingStatus;
  staff_note: string;
  expected_revision: number;
}

export interface F60Result {
  id: string;
  status: string;
  updated_at: string;
}

export async function updateMissingPart(request: F60Request): Promise<F60Result> {
  return api<F60Result>(`/v1/staff/missing-parts/${request.item_id}`, {
    method: "PATCH",
    body: JSON.stringify({
      status: request.status,
      staff_note: request.staff_note,
      expected_revision: request.expected_revision,
    }),
  });
}
