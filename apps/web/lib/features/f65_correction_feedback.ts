// F65 Correction feedback — typed client for POST /v1/staff/corrections/{id}/eval-case.
//
// Admin-only. Submits only typed identifiers + the controlled expected label — never private
// customer text. The server curates a REVIEWED correction into an anonymized eval case.

import { api } from "@/lib/api";

export interface F65Request {
  correction_id: string;
  case_id: string;
  approved_expected: string;
}

export interface F65Result {
  case_id: string;
  source_revision: number;
  approved_by: string;
}

export async function curateCorrection(request: F65Request): Promise<F65Result> {
  return api<F65Result>(`/v1/staff/corrections/${request.correction_id}/eval-case`, {
    method: "POST",
    body: JSON.stringify(request),
  });
}
