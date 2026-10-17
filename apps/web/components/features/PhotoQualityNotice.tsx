"use client";

import { useState, type JSX } from "react";

import type { ApiError } from "@/lib/api";
import { BLOCKING_ISSUES, type F16Request, type F16Result } from "@/lib/features/f16_photo_quality_feedback";

// F16 Photo quality feedback — displays the local pre-check verdict and actionable retake
// guidance. Blocking issues (unsupported/undecodable/too large) must be fixed before upload;
// everything else is advisory, so a slightly blurry/dark/low-res photo can still be submitted.
// The control submits only typed identifiers (image bytes + media type) — never a
// browser-authored compatibility fact.
const GUIDANCE: Record<string, string> = {
  unsupported_format: "That file type isn’t supported. Use a JPEG, PNG or WebP photo.",
  format_mismatch: "The file contents don’t match its type. Re-save the photo and try again.",
  undecodable_image: "We couldn’t read that image. Please retake the nameplate photo.",
  image_too_large: "That image is too large. Use a smaller photo of the nameplate.",
  low_resolution: "The photo looks low-resolution — move closer so the nameplate fills the frame.",
  too_dark: "The photo looks dark — add light and avoid shadows across the nameplate.",
  possible_blur: "The photo may be blurry — hold steady and refocus. You can still submit it.",
};

function isBlocking(issues: string[]): boolean {
  return issues.some((i) => BLOCKING_ISSUES.has(i));
}

export function PhotoQualityNotice(props: {
  value: F16Result | null;
  loading: boolean;
  error: ApiError | null;
  onAction: (request: F16Request) => Promise<void>;
}): JSX.Element {
  const { value, loading, error, onAction } = props;
  const [busy, setBusy] = useState(false);

  async function onFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy(true);
    try {
      const bytes = await file.arrayBuffer();
      await onAction({ image_bytes: bytes, media_type: file.type });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-label="Photo quality check" data-testid="photo-quality-notice">
      <label>
        Check a nameplate photo before sending
        <input type="file" accept="image/jpeg,image/png,image/webp" onChange={onFile} disabled={busy || loading} />
      </label>

      {loading || busy ? <p data-testid="pq-loading">Checking the photo…</p> : null}

      {error ? (
        <p role="alert">
          {error.message}
          {error.requestId ? ` (ref ${error.requestId})` : ""}
        </p>
      ) : null}

      {!loading && !busy && !error && value === null ? (
        <p data-testid="pq-empty">Choose a nameplate photo and we’ll check it is readable first.</p>
      ) : null}

      {value !== null ? (
        <div data-testid="pq-result" data-readable={value.readable}>
          {isBlocking(value.issues) ? (
            <p role="alert">Please retake the photo before sending:</p>
          ) : value.issues.length > 0 ? (
            <p role="note">The photo is usable. A few tips to improve the reading:</p>
          ) : (
            <p role="status">This photo looks good — go ahead and send it.</p>
          )}
          <p data-testid="pq-dimensions">
            {value.width}×{value.height} px
          </p>
          {value.issues.length > 0 ? (
            <ul>
              {value.issues.map((code) => (
                <li key={code} data-advisory={!BLOCKING_ISSUES.has(code)}>
                  {GUIDANCE[code] ?? code}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
