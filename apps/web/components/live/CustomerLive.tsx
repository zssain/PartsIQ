"use client";

import { useCallback, useEffect, useRef, useState, type JSX } from "react";

import { ApiError } from "@/lib/api";
import { createEnquiry, getEnquiry } from "@/lib/live";
import type { EnquiryView, MessageView } from "@/lib/contracts";
import { CustomerProgress } from "@/components/visibility/CustomerProgress";

// LIVE customer flow. The customer types a request and submits it via createEnquiry (202 → id);
// we then mount CustomerProgress (which polls the PERSISTED timeline) and poll the enquiry snapshot
// itself to render its messages. The published recommendation reply is shown ONLY when the server
// reports status==approved — never speculatively. On a send failure the composer text is PRESERVED
// (we never clear the input on error) so the customer never loses their words. Honest states:
// idle / submitting / loading / error+retry (with request id) / not-available (foreign → 404).

const BASE_DELAY_MS = 2500;
const MAX_DELAY_MS = 15000;
const HIDDEN_DELAY_MS = 30000;
const PERMISSION = new Set([401, 403, 404]);

function recommendation(enquiry: EnquiryView): MessageView | undefined {
  // The published reply is the LAST recommendation message the server returned (publication is
  // gated server-side; it only appears after approval).
  return [...enquiry.messages].reverse().find((m) => m.kind === "recommendation");
}

export function CustomerLive({
  enquiryId,
  onCreated,
}: {
  // When a live enquiry already exists for this session, drive it; otherwise show the composer.
  enquiryId: string | null;
  onCreated: (id: string) => void;
}): JSX.Element {
  const [draft, setDraft] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<ApiError | string | null>(null);

  const submit = useCallback(
    async (event: React.FormEvent) => {
      event.preventDefault();
      const text = draft.trim();
      if (!text || submitting) return;
      setSubmitting(true);
      setSubmitError(null);
      try {
        const result = await createEnquiry({ text });
        // Only clear the composer on confirmed creation; a retry never duplicates (idempotency key).
        setDraft("");
        onCreated(result.id);
      } catch (err) {
        // PRESERVE the unsent text — do not clear the composer on error.
        setSubmitError(err instanceof ApiError ? err : "Could not submit your enquiry.");
      } finally {
        setSubmitting(false);
      }
    },
    [draft, submitting, onCreated],
  );

  if (enquiryId === null) {
    const errText =
      submitError instanceof ApiError
        ? `${submitError.message}${submitError.requestId ? ` (ref ${submitError.requestId})` : ""}`
        : submitError;
    return (
      <section aria-label="New enquiry" data-testid="customer-composer" className="pq-card">
        <h2 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: 6 }}>Describe the part you need</h2>
        <p className="pq-muted" style={{ fontSize: "0.9rem", marginBottom: 10 }}>
          Write in English or Arabic. A specialist reviews every recommendation before it is sent.
        </p>
        <form onSubmit={submit}>
          <textarea
            data-testid="enquiry-text"
            aria-label="Enquiry text"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="e.g. I need 2× air filters for a Corvane Air CA-110 (serial 800123)"
            rows={4}
            style={{ width: "100%", padding: 10, borderRadius: 10, resize: "vertical" }}
          />
          <div style={{ marginTop: 10 }}>
            <button
              type="submit"
              className="pq-btn pq-btn-primary"
              data-testid="enquiry-submit"
              disabled={submitting || draft.trim().length === 0}
            >
              {submitting ? "Submitting…" : "Submit enquiry"}
            </button>
          </div>
        </form>
        {errText ? (
          <p role="alert" data-testid="submit-error" style={{ marginTop: 10 }}>
            {errText} Your text is kept — try again.
          </p>
        ) : null}
      </section>
    );
  }

  return <CustomerEnquiry enquiryId={enquiryId} />;
}

function CustomerEnquiry({ enquiryId }: { enquiryId: string }): JSX.Element {
  const [enquiry, setEnquiry] = useState<EnquiryView | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const delayRef = useRef(BASE_DELAY_MS);

  const load = useCallback(
    async (signal?: AbortSignal) => {
      try {
        const view = await getEnquiry(enquiryId, signal);
        setEnquiry(view);
        setError(null);
        delayRef.current = BASE_DELAY_MS;
      } catch (err) {
        if (signal?.aborted) return;
        if (err instanceof ApiError) setError(err);
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
      await load(controller.signal);
      if (!active) return;
      if (error && PERMISSION.has(error.status)) return; // terminal: stop polling a denied resource
      const delay = document.hidden ? HIDDEN_DELAY_MS : delayRef.current;
      timer = setTimeout(tick, delay);
    };
    void tick();
    return () => {
      active = false;
      controller.abort();
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load]);

  if (error && PERMISSION.has(error.status)) {
    return (
      <section aria-label="Your enquiry" data-testid="customer-enquiry" className="pq-card">
        <p data-testid="enquiry-not-available">
          This enquiry is not available.{error.requestId ? ` (ref ${error.requestId})` : ""}
        </p>
      </section>
    );
  }

  if (error && enquiry === null) {
    return (
      <section aria-label="Your enquiry" data-testid="customer-enquiry" className="pq-card">
        <p role="alert">
          Could not load your enquiry. {error.message}
          {error.requestId ? ` (ref ${error.requestId})` : ""}
        </p>
        <button type="button" className="pq-btn pq-btn-ghost" onClick={() => void load()} data-testid="enquiry-retry">
          Retry
        </button>
      </section>
    );
  }

  const reply = enquiry ? recommendation(enquiry) : undefined;
  const approved = enquiry?.status === "approved";

  return (
    <div data-testid="customer-enquiry" style={{ display: "grid", gap: 16 }}>
      <CustomerProgress enquiryId={enquiryId} />

      <section aria-label="Conversation" className="pq-card">
        <h2 style={{ fontSize: "1.05rem", fontWeight: 700, marginBottom: 8 }}>Your conversation</h2>
        {enquiry === null ? (
          <p data-testid="enquiry-loading">Loading your enquiry…</p>
        ) : enquiry.messages.length === 0 ? (
          <p data-testid="messages-empty" className="pq-muted">
            Your request is in. We&rsquo;ll show replies here as they arrive.
          </p>
        ) : (
          <ul data-testid="messages" style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 8 }}>
            {enquiry.messages.map((m) => (
              <li key={m.id} data-kind={m.kind} className="pq-message">
                {m.body}
              </li>
            ))}
          </ul>
        )}
      </section>

      {approved && reply ? (
        <section aria-label="Published recommendation" data-testid="approved-reply" className="pq-card" style={{ borderLeft: "3px solid var(--pq-ok, #2bb673)" }}>
          <h2 style={{ fontSize: "1.05rem", fontWeight: 700, marginBottom: 6 }}>Recommendation (reviewer-approved)</h2>
          <p>{reply.body}</p>
        </section>
      ) : null}
    </div>
  );
}
