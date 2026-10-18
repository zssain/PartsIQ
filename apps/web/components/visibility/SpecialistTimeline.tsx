"use client";

import { useCallback, useEffect, useState, type JSX } from "react";

import { ApiError } from "@/lib/api";
import { getTimeline, type TimelineEvent, type TimelineView } from "@/lib/live";

// SpecialistTimeline (visibility panel 2). The staff-facing view of the SAME persisted timeline
// the customer sees, but with each step's label, status, timestamp and a concise evidence line
// (step + outcome). Failures and retries are shown when present. This renders ONLY observable
// step inputs/outputs/tool-result summaries — never any hidden model chain-of-thought. Honest
// states: loading / empty / error+retry / permission (401/403/404), each surfacing the request id.

const PERMISSION = new Set([401, 403, 404]);

const STATUS_LABEL: Record<TimelineEvent["status"], string> = {
  pending: "Pending",
  running: "Running",
  done: "Done",
  waiting: "Waiting",
  failed: "Failed",
};

export function SpecialistTimeline({ enquiryId }: { enquiryId: string }): JSX.Element {
  const [view, setView] = useState<TimelineView | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setView(await getTimeline(enquiryId));
    } catch (err) {
      if (err instanceof ApiError) setError(err);
    } finally {
      setLoading(false);
    }
  }, [enquiryId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading && view === null) {
    return (
      <section aria-label="Specialist timeline" data-testid="specialist-timeline" className="pq-card">
        <p data-testid="timeline-loading">Loading the specialist timeline…</p>
      </section>
    );
  }

  if (error && PERMISSION.has(error.status)) {
    return (
      <section aria-label="Specialist timeline" data-testid="specialist-timeline" className="pq-card">
        <p data-testid="timeline-permission">
          The specialist timeline requires a signed-in staff session.
          {error.requestId ? ` (ref ${error.requestId})` : ""}
        </p>
      </section>
    );
  }

  if (error) {
    return (
      <section aria-label="Specialist timeline" data-testid="specialist-timeline" className="pq-card">
        <p role="alert">
          Could not load the timeline. {error.message}
          {error.requestId ? ` (ref ${error.requestId})` : ""}
        </p>
        <button type="button" onClick={() => void load()} data-testid="timeline-retry">
          Retry
        </button>
      </section>
    );
  }

  if (view === null || view.events.length === 0) {
    return (
      <section aria-label="Specialist timeline" data-testid="specialist-timeline" className="pq-card">
        <p data-testid="timeline-empty">No pipeline steps recorded yet.</p>
      </section>
    );
  }

  return (
    <section aria-label="Specialist timeline" data-testid="specialist-timeline" className="pq-card">
      <h2 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: 10 }}>Specialist timeline</h2>
      <ol data-testid="timeline-events" style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {view.events.map((e, i) => (
          <li
            key={`${e.step}:${i}`}
            data-step={e.step}
            data-status={e.status}
            className="pq-check-row"
            style={{ display: "flex", flexDirection: "column", gap: 2, padding: "8px 0", borderTop: i === 0 ? undefined : "1px solid var(--pq-hairline, rgba(128,128,128,0.2))" }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <strong>{e.label}</strong>
              <span className="pq-chip" data-testid={`status-${e.step}`}>
                {STATUS_LABEL[e.status]}
              </span>
              {e.attempt && e.attempt > 1 ? (
                <span className="pq-chip" data-testid={`attempt-${e.step}`}>
                  attempt {e.attempt}
                </span>
              ) : null}
              <time className="pq-muted" style={{ fontSize: "0.8rem", marginLeft: "auto" }} dateTime={e.at}>
                {e.at}
              </time>
            </div>
            <p className="pq-muted" data-testid={`evidence-${e.step}`} style={{ fontSize: "0.85rem", margin: 0 }}>
              {e.detail ?? `${e.label} — ${STATUS_LABEL[e.status].toLowerCase()}`}
            </p>
          </li>
        ))}
      </ol>
    </section>
  );
}
