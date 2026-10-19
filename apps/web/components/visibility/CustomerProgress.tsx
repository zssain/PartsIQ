"use client";

import { useCallback, useEffect, useRef, useState, type JSX } from "react";

import { ApiError } from "@/lib/api";
import { getTimeline, type TimelineEvent, type TimelineView } from "@/lib/live";

// CustomerProgress (visibility panel 1). Drives an animated step list from the PERSISTED timeline
// events (GET /v1/enquiries/{id}/timeline), polled with bounded backoff. The animation follows
// ACTUAL event status — a step is only shown done/waiting/failed when the server records it, and
// the current step is highlighted. No fake spinner ever runs ahead of real state. Honest states:
// loading / empty / error+retry / permission (401/403/404), each surfacing the request id.

// The canonical customer-facing pipeline, in order. Server events are matched to these by `step`;
// any step the server has not yet recorded stays "upcoming" (never fabricated as done).
// Keys are the backend's canonical workflow step names (partsiq.core.contracts.WorkflowStep /
// the timeline events); labels are the customer-facing wording. Keeping the domain keys here lets
// each persisted event match its stage directly.
const PIPELINE: { step: string; label: string }[] = [
  { step: "intake", label: "Reading request" },
  { step: "identify", label: "Identifying" },
  { step: "search", label: "Finding parts" },
  { step: "plan", label: "Planning" },
  { step: "draft", label: "Drafting" },
  { step: "verify", label: "Checking" },
  { step: "review", label: "Waiting for review" },
];

const BASE_DELAY_MS = 2500;
const MAX_DELAY_MS = 15000;
const HIDDEN_DELAY_MS = 30000;
const PERMISSION = new Set([401, 403, 404]);

type Stage = "upcoming" | "running" | "done" | "waiting" | "failed";

function stageFor(event: TimelineEvent | undefined, isCurrent: boolean): Stage {
  if (!event) return isCurrent ? "running" : "upcoming";
  switch (event.status) {
    case "done":
      return "done";
    case "waiting":
      return "waiting";
    case "failed":
      return "failed";
    case "running":
      return "running";
    default:
      return isCurrent ? "running" : "upcoming";
  }
}

const STAGE_SYMBOL: Record<Stage, string> = {
  upcoming: "○",
  running: "◐",
  done: "●",
  waiting: "⏳",
  failed: "✕",
};

export function CustomerProgress({ enquiryId }: { enquiryId: string }): JSX.Element {
  const [view, setView] = useState<TimelineView | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const delayRef = useRef(BASE_DELAY_MS);

  const load = useCallback(
    async (signal?: AbortSignal) => {
      try {
        const next = await getTimeline(enquiryId, signal);
        setView(next);
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
      // A permission error is terminal — stop polling rather than hammer a denied endpoint.
      if (error && PERMISSION.has(error.status)) return;
      const delay = document.hidden ? HIDDEN_DELAY_MS : delayRef.current;
      timer = setTimeout(tick, delay);
    };
    void tick();
    return () => {
      active = false;
      controller.abort();
      clearTimeout(timer);
    };
    // `error` is intentionally omitted: it is read inside the loop to stop on permission denial,
    // and the effect re-arms its own timer. Re-subscribing on every error would restart polling.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load]);

  if (error && PERMISSION.has(error.status)) {
    return (
      <section aria-label="Your progress" data-testid="customer-progress" className="pq-card">
        <p data-testid="progress-permission">
          You do not have access to this enquiry&rsquo;s progress.
          {error.requestId ? ` (ref ${error.requestId})` : ""}
        </p>
      </section>
    );
  }

  if (error && view === null) {
    return (
      <section aria-label="Your progress" data-testid="customer-progress" className="pq-card">
        <p role="alert">
          Could not load progress. {error.message}
          {error.requestId ? ` (ref ${error.requestId})` : ""}
        </p>
        <button type="button" onClick={() => void load()} data-testid="progress-retry">
          Retry
        </button>
      </section>
    );
  }

  if (view === null) {
    return (
      <section aria-label="Your progress" data-testid="customer-progress" className="pq-card">
        <p data-testid="progress-loading">Loading the latest status…</p>
      </section>
    );
  }

  if (view.events.length === 0) {
    return (
      <section aria-label="Your progress" data-testid="customer-progress" className="pq-card">
        <p data-testid="progress-empty">Your request is queued. We&rsquo;ll show each step here as it happens.</p>
      </section>
    );
  }

  const byStep = new Map(view.events.map((e) => [e.step, e]));
  // The current step is the last one the server has recorded activity for (highest index present).
  let currentIndex = 0;
  PIPELINE.forEach((p, i) => {
    if (byStep.has(p.step)) currentIndex = i;
  });
  const waitingEvent = view.events.find((e) => e.status === "waiting");

  return (
    <section aria-label="Your progress" data-testid="customer-progress" className="pq-card">
      <ol data-testid="progress-steps" style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {PIPELINE.map((p, i) => {
          const event = byStep.get(p.step);
          const isCurrent = i === currentIndex;
          const stage = stageFor(event, isCurrent);
          return (
            <li
              key={p.step}
              data-step={p.step}
              data-stage={stage}
              data-current={isCurrent ? "true" : undefined}
              aria-current={isCurrent ? "step" : undefined}
              className={isCurrent ? "pq-step-top pq-sidebar-active" : "pq-step-top"}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "6px 0",
                fontWeight: isCurrent ? 700 : 400,
                opacity: stage === "upcoming" ? 0.55 : 1,
              }}
            >
              <span aria-hidden="true" data-testid={`stage-symbol-${p.step}`}>
                {STAGE_SYMBOL[stage]}
              </span>
              <span>{event?.label ?? p.label}</span>
              {event?.attempt && event.attempt > 1 ? (
                <span className="pq-chip" data-testid={`retry-${p.step}`}>
                  retry {event.attempt}
                </span>
              ) : null}
            </li>
          );
        })}
      </ol>
      {waitingEvent ? (
        <p data-testid="wait-reason" className="pq-muted" style={{ marginTop: 10 }}>
          {waitingEvent.detail ?? "Waiting for our team to review"}
        </p>
      ) : null}
    </section>
  );
}
