// F44 Conversation summary — typed client for the staff summary route (owner orchestrator).
//
// Staff-only. Requesting a summary returns 202; the current-revision summary is then read from
// the review view. Submits only typed identifiers. The summary is never shown to a customer.

import { api } from "@/lib/api";

export interface F44Request {
  enquiry_id: string;
  expected_revision: number;
}

export interface F44Result {
  summary: string;
  source_message_ids: string[];
  revision: number;
}

export async function requestSummary(request: F44Request): Promise<void> {
  await api<unknown>(
    `/v1/staff/enquiries/${request.enquiry_id}/summary?expected_revision=${request.expected_revision}`,
    { method: "POST" },
  );
}

// A displayed summary is stale once the enquiry has moved past the revision it summarized.
export function isStale(summaryRevision: number, currentRevision: number): boolean {
  return summaryRevision !== currentRevision;
}
