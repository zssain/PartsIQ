// F17 Multi-part enquiries — typed client for the per-item resolution view (owner orchestrator).
//
// The browser submits only typed identifiers (enquiry id + the revision it is acting on); the
// gateway validates role and forwards to the orchestrator internal resolver. No compatibility
// fact is authored in the browser — item status, candidates and allocation are decided
// server-side (the gateway route is BLOCKED until wired).

import { api } from "@/lib/api";

export type ItemStatus = "unresolved" | "needs_information" | "ready" | "unavailable";

export interface ItemState {
  id: string;
  configuration_id: number | null;
  candidate_part_ids: number[];
  selected_part_id: number | null;
  status: ItemStatus;
  request: {
    description: string;
    quantity: number | null;
  };
}

export interface F17Request {
  enquiry_id: string;
  expected_revision: number;
}

export interface F17Result {
  items: ItemState[];
  unresolved_item_ids: string[];
}

export function canApproveAll(result: F17Result): boolean {
  return result.unresolved_item_ids.length === 0;
}

export async function resolveItems(request: F17Request): Promise<F17Result> {
  return api<F17Result>(`/v1/enquiries/${request.enquiry_id}/items/resolve`, {
    method: "POST",
    body: JSON.stringify({ expected_revision: request.expected_revision }),
  });
}
