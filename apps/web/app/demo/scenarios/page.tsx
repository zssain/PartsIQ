import { ScanLine, Fingerprint, ShieldCheck, PackageCheck, ArrowUpRight, Radio } from "lucide-react";
import { type JSX } from "react";

import { TiltCard } from "@/components/ui/TiltCard";
import { Reveal } from "@/components/ui/Reveal";
import { FixtureBanner } from "@/components/visibility/FixtureBanner";
import { SCENARIOS } from "@/lib/demo/engine";

// Guided scenarios (secondary): four scripted seed-42 walkthroughs that run entirely in the browser.
// The real application is the workspace (/workspace); these are explanations, not the product.
export default function DemoPage(): JSX.Element {
  return (
    <div className="pq-container" style={{ paddingTop: 40, paddingBottom: 40 }}>
      <Reveal className="pq-page-top">
        <span className="pq-badge" style={{ marginBottom: 14 }}>GUIDED SCENARIOS / SCRIPTED WALKTHROUGHS</span>
        <h1 style={{ fontSize: "clamp(1.8rem, 4vw, 2.8rem)", fontWeight: 800 }}>
          A different question.<br /><span className="pq-gradient-text">The same thoughtful process.</span>
        </h1>
        <p className="pq-muted" style={{ maxWidth: 620, marginTop: 12 }}>
          Scripted explanations of identification, compatibility, fulfilment, deterministic verification and the
          human approval gate, using fabricated data only. For the real application — your own enquiries, live
          runs, agent collaboration and human review — open the workspace.
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

      <Reveal delay={120}>
        <a href="/demo" data-testid="live-demo-link" style={{ display: "block", marginTop: 20 }}>
          <TiltCard className="pq-scenario-card" style={{ display: "flex", gap: 16, alignItems: "center", justifyContent: "space-between", flexWrap: "wrap" }} max={4}>
            <div>
              <div className="pq-scenario-top" style={{ marginBottom: 8 }}><Radio size={28} strokeWidth={1.3} aria-hidden="true" /></div>
              <h2 style={{ fontSize: "1.2rem", fontWeight: 700, margin: "0 0 6px" }}>Open the workspace demo</h2>
              <p className="pq-muted" style={{ fontSize: "0.92rem", maxWidth: 560 }}>
                Send your own enquiry, watch a guided run or an agent collaboration, pause or instruct it, then
                preview the reviewer and administrator screens — in a private, disposable sandbox.
              </p>
            </div>
            <div className="pq-text-link">Try the demo <ArrowUpRight size={16} /></div>
          </TiltCard>
        </a>
      </Reveal>
    </div>
  );
}
