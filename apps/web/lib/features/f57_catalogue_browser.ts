// F57 Catalogue browser — typed client for GET /v1/catalogue/parts (owner gateway).
//
// Read-only over the active published catalogue. Submits only typed filter identifiers; the
// query is a plain filter string, never a compatibility fact.

import { api } from "@/lib/api";

export interface PartView {
  id: number;
  part_number: string;
  name_en: string;
  name_ar: string;
  category: string;
  superseded_by: string | null;
  fitment: string[];
  sources: string[];
}

export interface F57Request {
  query?: string | null;
  model_id?: number | null;
  category?: string | null;
  cursor?: string | null;
  limit?: number;
}

export interface F57Result {
  parts: PartView[];
  next_cursor: string | null;
  version_id: string;
}

export async function browseCatalogue(request: F57Request = {}): Promise<F57Result> {
  const params = new URLSearchParams();
  if (request.query) params.set("query", request.query);
  if (request.model_id != null) params.set("model_id", String(request.model_id));
  if (request.category) params.set("category", request.category);
  if (request.cursor) params.set("cursor", request.cursor);
  if (request.limit) params.set("limit", String(request.limit));
  const qs = params.toString();
  return api<F57Result>(`/v1/catalogue/parts${qs ? `?${qs}` : ""}`);
}

export async function partDetail(partNumber: string): Promise<PartView> {
  return api<PartView>(`/v1/catalogue/parts/${encodeURIComponent(partNumber)}`);
}
