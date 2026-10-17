// F55 Saved machines — typed client for /v1/machines (owner gateway).
//
// The browser submits only typed identifiers (label, model id, serial, idempotency key); it
// never authors a configuration or compatibility fact. A saved machine prefills a new enquiry
// but the workflow always re-identifies against the current catalogue.

import { api } from "@/lib/api";

export interface F55Request {
  label: string;
  model_id: number;
  serial_text: string;
  idempotency_key: string;
}

export interface F55Result {
  id: string;
  label: string;
  model_id: number;
  serial_text: string;
}

export async function saveMachine(request: F55Request): Promise<F55Result> {
  return api<F55Result>("/v1/machines", { method: "POST", body: JSON.stringify(request) });
}

export async function listMachines(): Promise<F55Result[]> {
  return api<F55Result[]>("/v1/machines");
}

export async function renameMachine(id: string, label: string): Promise<F55Result> {
  return api<F55Result>(`/v1/machines/${id}?label=${encodeURIComponent(label)}`, { method: "PATCH" });
}

export async function archiveMachine(id: string): Promise<void> {
  await api<void>(`/v1/machines/${id}`, { method: "DELETE" });
}
