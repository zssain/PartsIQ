"use client";

import { useCallback, useEffect, useRef, useState, type JSX } from "react";

import { api, ApiError } from "@/lib/api";
import type { EnquiryView, MessageView } from "@/lib/contracts";
import { Progress } from "@/components/chat/Progress";
import { PhotoQualityNotice } from "@/components/features/PhotoQualityNotice";
import { assessPhoto, type F16Request, type F16Result } from "@/lib/features/f16_photo_quality_feedback";
import { ItemList } from "@/components/features/ItemList";
import { resolveItems, type F17Request, type F17Result } from "@/lib/features/f17_multi_part_enquiries";

// Customer chat (F09, F11, F18, F53). Polls the enquiry with an AbortController and bounded
// exponential backoff, throttling while the tab is hidden; renders customer/clarification/
// status messages immediately and recommendation messages only when the server returns them
// (publication is gated server-side). React escapes all message text. On a recoverable send
// failure the unsent text is preserved so the customer never loses their words.
const BASE_DELAY_MS = 2000;
const MAX_DELAY_MS = 15000;
const HIDDEN_DELAY_MS = 30000;
const RETRYABLE = new Set(["DEPENDENCY_UNAVAILABLE", "QUOTA_EXCEEDED"]);

export function Chat({ enquiryId }: { enquiryId: string }): JSX.Element {
  const [enquiry, setEnquiry] = useState<EnquiryView | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [pollFailed, setPollFailed] = useState(false);
  const [draft, setDraft] = useState("");
  const [sendError, setSendError] = useState<string | null>(null);
  // F16: optional local photo-quality pre-check before the customer uploads a nameplate photo.
  const [photoQuality, setPhotoQuality] = useState<F16Result | null>(null);
  // F17: per-item resolution view for multi-part enquiries (status, candidates, readiness gate).
  const [items, setItems] = useState<F17Result | null>(null);
  const [itemsError, setItemsError] = useState<ApiError | null>(null);
  const delayRef = useRef(BASE_DELAY_MS);

  const checkPhoto = useCallback(async (request: F16Request) => {
    setPhotoQuality(await assessPhoto(request));
  }, []);

  const resolveItemsAction = useCallback(async (request: F17Request) => {
    setItemsError(null);
    try {
      setItems(await resolveItems(request));
    } catch (err) {
      setItemsError(err instanceof ApiError ? err : null);
    }
  }, []);

  const poll = useCallback(
    async (signal: AbortSignal) => {
      try {
        const view = await api<EnquiryView>(`/v1/enquiries/${enquiryId}`, { signal });
        setEnquiry(view);
        setLastUpdated(view.updated_at);
        setPollFailed(false);
        delayRef.current = BASE_DELAY_MS; // reset backoff on success
      } catch (err) {
        if (signal.aborted) return;
        setPollFailed(true); // retain last state; offer retry (F18/F53)
        delayRef.current = Math.min(delayRef.current * 2, MAX_DELAY_MS);
      }
    },
    [enquiryId],
  );

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    let controller = new AbortController();
    let active = true;

    const tick = async () => {
      controller = new AbortController();
      await poll(controller.signal);
      if (!active) return;
      const delay = document.hidden ? HIDDEN_DELAY_MS : delayRef.current;
      timer = setTimeout(tick, delay);
    };
    tick();

    return () => {
      active = false;
      controller.abort();
      clearTimeout(timer);
    };
  }, [poll]);

  async function send(event: React.FormEvent) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || !enquiry) return;
    setSendError(null);
    try {
      await api<MessageView>(`/v1/enquiries/${enquiryId}/messages`, {
        method: "POST",
        headers: { "idempotency-key": crypto.randomUUID() },
        body: JSON.stringify({ text, expected_revision: enquiry.revision }),
      });
      setDraft(""); // clear only on confirmed persistence (retry never duplicates)
    } catch (err) {
      // Preserve the unsent text; surface safe, bilingual-ready guidance.
      if (err instanceof ApiError && RETRYABLE.has(err.code)) {
        setSendError("We could not send that just now. Your text is kept — try again.");
      } else {
        setSendError(err instanceof ApiError ? err.message : "Could not send your message.");
      }
    }
  }

  const messages: MessageView[] = enquiry?.messages ?? [];

  return (
    <div>
      <Progress
        enquiry={enquiry}
        lastUpdated={lastUpdated}
        pollFailed={pollFailed}
        onRetry={() => {
          const c = new AbortController();
          void poll(c.signal);
        }}
      />
      <ul data-testid="messages">
        {messages.map((m) => (
          <li key={m.id} data-kind={m.kind}>
            {m.body}
          </li>
        ))}
      </ul>
      <PhotoQualityNotice value={photoQuality} loading={false} error={null} onAction={checkPhoto} />
      <ItemList value={items} loading={false} error={itemsError} onAction={resolveItemsAction} />
      <form onSubmit={send}>
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Describe the part you need (English or Arabic)"
        />
        <button type="submit">Send</button>
      </form>
      {sendError ? <p role="alert">{sendError}</p> : null}
    </div>
  );
}
