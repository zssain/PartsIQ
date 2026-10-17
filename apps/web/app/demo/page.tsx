import { type JSX } from "react";

import { TiltCard } from "@/components/ui/TiltCard";
import { Reveal } from "@/components/ui/Reveal";
import { SCENARIOS } from "@/lib/demo/engine";

// Demo hub: pick one of the four seed-42 synthetic scenarios. Runs entirely offline — no backend
// session required — so the walkthrough works anywhere.
export default function DemoPage(): JSX.Element {
  return (
    <div className="pq-container" style={{ paddingTop: 40, paddingBottom: 40 }}>
      <Reveal>
        <span className="pq-badge" style={{ marginBottom: 14 }}>Offline · synthetic · seed 42</span>
        <h1 style={{ fontSize: "clamp(1.8rem, 4vw, 2.8rem)", fontWeight: 800 }}>
          Walk through a <span className="pq-gradient-text">live scenario</span>
        </h1>
        <p className="pq-muted" style={{ maxWidth: 620, marginTop: 12 }}>
          Each scenario steps through identification, compatibility, fulfilment, deterministic verification and the
          human approval gate — using fabricated data only. Pick one to begin.
        </p>
      </Reveal>

      <div style={{ display: "grid", gap: 18, gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", marginTop: 28 }}>
        {SCENARIOS.map((s, i) => (
          <Reveal key={s.id} delay={i * 90}>
            <a href={`/demo/${s.id}`} data-testid={`scenario-${s.id}`} style={{ display: "block", height: "100%" }}>
              <TiltCard style={{ padding: 22, height: "100%" }}>
                <div style={{ fontSize: "2rem" }} aria-hidden="true">{s.icon}</div>
                <h2 style={{ fontSize: "1.2rem", fontWeight: 700, margin: "10px 0 8px" }}>{s.title}</h2>
                <p className="pq-muted" style={{ fontSize: "0.92rem", minHeight: 44 }}>{s.blurb}</p>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 10 }}>
                  {s.tags.map((t) => <span key={t} className="pq-chip">{t}</span>)}
                </div>
                <div className="pq-btn pq-btn-ghost" style={{ marginTop: 16 }}>Run walkthrough →</div>
              </TiltCard>
            </a>
          </Reveal>
        ))}
      </div>
    </div>
  );
}
