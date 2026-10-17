// F58 Catalogue imports — typed client for the staff import routes (owner gateway/worker).
//
// The browser only records a batch and requests validation; the worker parses the file and
// produces the dry-run report. The browser never parses catalogue rows or publishes.

import { api } from "@/lib/api";

export interface ImportErrorView {
  row: number | null;
  code: string;
  detail: string;
}

export interface F58Result {
  valid: boolean;
  row_count: number;
  errors: ImportErrorView[];
}

export interface F58Request {
  batch_id: string;
}

export async function createImport(
  filename: string,
  media_type: string,
  size_bytes: number,
): Promise<{ batch_id: string }> {
  return api<{ batch_id: string }>("/v1/staff/imports", {
    method: "POST",
    body: JSON.stringify({ filename, media_type, size_bytes }),
  });
}

export async function requestValidate(batchId: string): Promise<{ job_id: string }> {
  return api<{ job_id: string }>(`/v1/staff/imports/${batchId}/validate`, { method: "POST" });
}

export async function getReport(batchId: string): Promise<F58Result> {
  return api<F58Result>(`/v1/staff/imports/${batchId}`);
}
