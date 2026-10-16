"use client";

import { useState, type JSX } from "react";

import { api, ApiError } from "@/lib/api";
import type { AttachmentView } from "@/lib/contracts";

// Private nameplate upload (F13). Client validates the MIME up front, asks the gateway for a
// signed upload ticket, PUTs the bytes straight to Storage (the narrow browser exception),
// then confirms so the worker validates the real bytes + magic type. The signing/validation
// authority stays server-side; this only drives the UI and progress.
const ALLOWED = new Set(["image/jpeg", "image/png", "image/webp"]);
const MAX_BYTES = 10 * 1024 * 1024;

type Phase = "idle" | "requesting" | "uploading" | "confirming" | "done" | "error";

interface UploadTicket {
  attachment_id: string;
  upload_url: string;
  expires_at: string;
}

export function UploadCard({
  enquiryId,
  expectedRevision,
  onConfirmed,
}: {
  enquiryId: string;
  expectedRevision: number;
  onConfirmed: (attachment: AttachmentView) => void;
}): JSX.Element {
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<string | null>(null);

  async function onFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setError(null);
    if (!ALLOWED.has(file.type)) {
      setError("Please choose a JPEG, PNG or WebP image.");
      setPhase("error");
      return;
    }
    if (file.size > MAX_BYTES) {
      setError("That image is larger than 10 MB.");
      setPhase("error");
      return;
    }
    try {
      setPhase("requesting");
      const ticket = await api<UploadTicket>("/v1/uploads", {
        method: "POST",
        body: JSON.stringify({
          enquiry_id: enquiryId,
          expected_revision: expectedRevision,
          media_type: file.type,
          size_bytes: file.size,
        }),
      });
      setPhase("uploading");
      await fetch(ticket.upload_url, { method: "PUT", body: file, headers: { "content-type": file.type } });
      setPhase("confirming");
      const attachment = await api<AttachmentView>(`/v1/attachments/${ticket.attachment_id}/confirm`, {
        method: "POST",
      });
      onConfirmed(attachment);
      setPhase("done");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed. Please try again.");
      setPhase("error");
    }
  }

  return (
    <div data-testid="upload-card">
      <label>
        Attach a nameplate photo
        <input type="file" accept="image/jpeg,image/png,image/webp" onChange={onFile} />
      </label>
      <p data-testid="upload-phase">{phase}</p>
      {error ? <p role="alert">{error}</p> : null}
    </div>
  );
}
