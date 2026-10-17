// F59 Catalogue versioning — typed client for POST /v1/staff/catalogue/publish (owner catalogue).
//
// Staff-only. The browser submits only typed ids (candidate version, the expected active
// version for optimistic concurrency, and an idempotency key); it never authors catalogue
// records. The gateway queues the publish to the worker and returns a durable job id.

import { api } from "@/lib/api";

export interface F59Request {
  version_id: string;
  expected_active_version_id: string;
  idempotency_key: string;
}

export interface F59Result {
  version_id: string;
  published_at: string;
  record_count: number;
}

export interface PublishAck {
  job_id: string;
}

export async function publishVersion(request: F59Request): Promise<PublishAck> {
  return api<PublishAck>("/v1/staff/catalogue/publish", {
    method: "POST",
    body: JSON.stringify(request),
  });
}
