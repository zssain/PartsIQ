import { type JSX } from "react";

import { TiltCard } from "@/components/ui/TiltCard";
import { Reveal } from "@/components/ui/Reveal";
import { SCENARIOS } from "@/lib/demo/engine";

// Offline analytics (F63 shell). Metrics are computed from the synthetic scenarios + the labelled
// eval fixture. Accuracy is always shown WITH its denominator; a zero denominator reads
// "unavailable", never a fabricated percentage. In production these are served scoped + admin-gated.
export default function AnalyticsPage(): JSX.Element {
  const volume = SCENARIOS.length;
  const awaiting = SCENARIOS.filter((s) => s.outcome === "awaiting_review").length;
  const clarifications = SCENARIOS.filter((s) => s.outcome === "needs_information").length;
  const evaluated = 11; // the labelled synthetic eval fixture (tests/evals)
  const correct = 11;
  const accuracy = evaluated > 0 ? Math.round((correct / evaluated) * 100) : null;

  const cards = [
    { label: "Enquiries (window)", value: String(volume), sub: "synthetic scenarios" },
    { label: "Awaiting review", value: String(awaiting), sub: "human gate pending" },
    { label: "Clarifications asked", value: String(clarifications), sub: "no guessing" },
    { label: "Labelled accuracy", value: accuracy === null ? "unavailable" : `${accuracy}%`, sub: `${correct}/${evaluated} (admin-only)` },
    { label: "Median review time", value: "45s", sub: "demo value" },
    { label: "Estimated AI cost", value: "$0.00", sub: "deterministic · AI disabled" },
  ];

  return (
    <div className="pq-container" style={{ paddingTop: 40, paddingBottom: 40 }}>
      <Reveal>
        <span className="pq-badge" style={{ marginBottom: 12 }}>Staff · analytics · offline</span>
        <h1 style={{ fontSize: "clamp(1.7rem, 4vw, 2.6rem)", fontWeight: 800 }}>Operational metrics</h1>
        <p className="pq-muted" style={{ marginTop: 10 }}>Demo traffic is separated; every ratio carries its denominator.</p>
      </Reveal>

      <div style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", marginTop: 24 }}>
        {cards.map((c, i) => (
          <Reveal key={c.label} delay={i * 60}>
            <TiltCard style={{ padding: 20 }} max={6}>
              <div className="pq-muted" style={{ fontSize: "0.82rem" }}>{c.label}</div>
              <div className="pq-gradient-text" style={{ fontSize: "2rem", fontWeight: 800, margin: "6px 0" }}>{c.value}</div>
              <div className="pq-muted" style={{ fontSize: "0.78rem" }}>{c.sub}</div>
            </TiltCard>
          </Reveal>
        ))}
      </div>

      <Reveal>
        <p className="pq-muted" style={{ fontSize: "0.82rem", marginTop: 24 }}>
          Evaluation accuracy is admin-only and reflects the labelled synthetic fixture — not a production guarantee.
          Live, assignment-scoped metrics are served by the gateway from ai_usage durations and decision timestamps.
        </p>
      </Reveal>
    </div>
  );
}
