// F29 Evidence page viewer — typed client for POST /v1/staff/evidence/open (owner gateway).
//
// Submits only typed identifiers (enquiry id, the cited evidence id, and the revision under
// review) — never a Storage key. The gateway authorizes and returns a short-lived worker-signed
// PDF URL to the exact cited page; every document is labelled synthetic.

import { api } from "@/lib/api";

export interface F29Request {
  enquiry_id: string;
  evidence_id: string;
  expected_revision: number;
}

export interface F29Result {
  url: string;
  page_number: number;
  expires_at: string;
  synthetic: boolean;
}

export async function openEvidence(request: F29Request): Promise<F29Result> {
  return api<F29Result>("/v1/staff/evidence/open", {
    method: "POST",
    body: JSON.stringify(request),
  });
}
