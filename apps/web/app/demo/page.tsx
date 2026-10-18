import { ScanLine, Fingerprint, ShieldCheck, PackageCheck, ArrowUpRight } from "lucide-react";
import { type JSX } from "react";

import { TiltCard } from "@/components/ui/TiltCard";
import { Reveal } from "@/components/ui/Reveal";
import { FixtureBanner } from "@/components/visibility/FixtureBanner";
import { SCENARIOS } from "@/lib/demo/engine";

// Demo hub: pick one of the four seed-42 synthetic scenarios. Runs entirely offline — no backend
// session required — so the walkthrough works anywhere.
export default function DemoPage(): JSX.Element {
  return (
    <div className="pq-container" style={{ paddingTop: 40, paddingBottom: 40 }}>
      <Reveal className="pq-page-top">
        <span className="pq-badge" style={{ marginBottom: 14 }}>THE WORKSPACE / SYNTHETIC DEMO</span>
        <h1 style={{ fontSize: "clamp(1.8rem, 4vw, 2.8rem)", fontWeight: 800 }}>
          A different question.<br /><span className="pq-gradient-text">The same thoughtful process.</span>
        </h1>
        <p className="pq-muted" style={{ maxWidth: 620, marginTop: 12 }}>
          Each scenario steps through identification, compatibility, fulfilment, deterministic verification and the
          human approval gate — using fabricated data only. Pick one to begin.
        </p>
        <div style={{ marginTop: 14 }}>
          <FixtureBanner />
        </div>
      </Reveal>

      <div style={{ display: "grid", gap: 18, gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 420px), 1fr))", marginTop: 28 }}>
        {SCENARIOS.map((s, i) => (
          <Reveal key={s.id} delay={i * 90}>
            <a href={`/demo/${s.id}`} data-testid={`scenario-${s.id}`} style={{ display: "block", height: "100%" }}>
              <TiltCard className="pq-scenario-card" style={{ height: "100%" }} max={4}>
                <div className="pq-scenario-top"><span>0{i + 1}</span>{[ScanLine, Fingerprint, ShieldCheck, PackageCheck].map((Icon, n) => n === i ? <Icon key={n} size={28} strokeWidth={1.3} aria-hidden="true" /> : null)}</div>
                <h2 style={{ fontSize: "1.2rem", fontWeight: 700, margin: "10px 0 8px" }}>{s.title}</h2>
                <p className="pq-muted" style={{ fontSize: "0.92rem", minHeight: 44 }}>{s.blurb}</p>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 10 }}>
                  {s.tags.map((t) => <span key={t} className="pq-chip">{t}</span>)}
                </div>
                <div className="pq-text-link" style={{ marginTop: 22 }}>Explore this scenario <ArrowUpRight size={16} /></div>
              </TiltCard>
            </a>
          </Reveal>
        ))}
      </div>
    </div>
  );
}
