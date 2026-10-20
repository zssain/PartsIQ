"use client";

import { useRouter } from "next/navigation";
import { useState, type JSX } from "react";
import { ArrowUpRight, ArrowRight, ScanLine, Layers3, ShieldCheck, PackageCheck, Languages, FileCheck2, Fingerprint, Command } from "lucide-react";
import { BrandLogo } from "@/components/BrandLogo";
import { TiltCard } from "@/components/ui/TiltCard";
import { Reveal } from "@/components/ui/Reveal";
import { startAnonymousDemo } from "@/lib/auth";

const JOURNEY = [
  { icon: ScanLine, title: "Start with what you have.", text: "A part number, a message, a nameplate photo. Send your enquiry in English or Arabic." },
  { icon: Layers3, title: "Find the right fit.", text: "PartsIQ identifies the machine and retrieves only catalogue-compatible parts." },
  { icon: PackageCheck, title: "See the whole picture.", text: "Explore stock across warehouses, evidence and a clear fulfilment plan." },
  { icon: ShieldCheck, title: "Keep a human in control.", text: "A human reviewer must approve before anything is published to you." },
];

export default function LandingPage(): JSX.Element {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  async function onStartDemo() {
    setBusy(true);
    try { await startAnonymousDemo(); } catch { /* The existing synthetic walkthrough also works offline. */ }
    router.push("/demo");
  }
  return (
    <div className="pq-landing">
      <section className="pq-editorial-hero pq-container">
        <div className="pq-hero-copy">
          <span className="pq-eyebrow"><span className="pq-signal" /> PARTS INTELLIGENCE, WITH PURPOSE</span>
          <h1>The right part.<br />The whole <em>picture.</em></h1>
          <p className="pq-lead">From an uncertain enquiry to a considered answer. Identify, verify, and review spare parts in one connected workspace.</p>
          <div className="pq-actions">
            <button className="pq-btn pq-btn-primary" disabled={busy} onClick={onStartDemo}>{busy ? "Starting…" : "Start demo"}<ArrowUpRight size={17} /></button>
            <a href="/architecture" className="pq-text-link">Explore the architecture <ArrowRight size={16} /></a>
          </div>
          <div className="pq-hero-proof"><span><ShieldCheck size={15} /> Human approved</span><span><Languages size={15} /> English + العربية</span></div>
          <p data-testid="synthetic-notice" role="note" className="pq-disclosure">Independent synthetic demonstration. All data is fabricated; not affiliated with any real distributor. No accuracy or delivery guarantee.</p>
        </div>
        <div className="pq-object-scene">
          <div className="pq-orbit" aria-hidden="true" />
          <div className="pq-object-caption"><span>THE INTELLIGENCE CARD</span><span>01 / PARTSIQ</span></div>
          <TiltCard className="pq-foil-card" max={12}>
            <div className="pq-foil-top"><BrandLogo compact /><Fingerprint size={27} strokeWidth={1} /></div>
            <div className="pq-part-art" aria-hidden="true"><div className="pq-part-ring"><div /><div /><div /></div><span className="pq-crosshair pq-crosshair-a">+</span><span className="pq-crosshair pq-crosshair-b">+</span><span className="pq-art-label">PRECISION IN EVERY CONNECTION</span></div>
            <div className="pq-foil-body"><span className="pq-eyebrow">ILLUSTRATIVE CATALOGUE PART</span><h2>Air filter element</h2><div className="pq-foil-meta"><bdi>CA-AF-8973</bdi><span>CA-110 · Configuration A</span></div></div>
            <div className="pq-foil-bottom"><span><ShieldCheck size={15} /> Evidence-led identification</span><ArrowUpRight size={19} /></div>
          </TiltCard>
          <div className="pq-object-foot"><span>MOVE YOUR CURSOR TO EXPLORE</span><span>↗ FOIL / 001</span></div>
        </div>
        <div className="pq-hero-bottom"><span>BUILT AROUND THE DETAILS THAT MATTER.</span><a href="#workspace">Discover the workspace ↓</a></div>
      </section>
      <div className="pq-capability-strip"><div className="pq-container"><span><ScanLine /> Machine identification</span><span><Layers3 /> Compatible parts</span><span><FileCheck2 /> Traceable evidence</span><span><ShieldCheck /> Human review</span></div></div>
      <section id="workspace" className="pq-container pq-section">
        <Reveal><div className="pq-section-heading"><div><span className="pq-eyebrow">01 / ONE CONNECTED WORKSPACE</span><h2>Less searching.<br /><em>More understanding.</em></h2></div><p className="pq-muted">Every enquiry has a story. Keep the conversation, compatible parts, and the evidence behind them together.</p></div></Reveal>
        <Reveal><div className="pq-workspace-preview">
          <aside className="pq-preview-sidebar"><span className="pq-eyebrow">WORKSPACE</span><a href="/workspace/review" className="pq-sidebar-active"><Command size={16} /> Review inbox <span>04</span></a><a href="/workspace/catalogue"><Layers3 size={16} /> Catalogue</a><a href="/workspace/enquiries"><FileCheck2 size={16} /> Enquiry history</a><div className="pq-sidebar-note"><span className="pq-signal" /> Synthetic workspace<br /><small>Explore safely. No real customer data.</small></div></aside>
          <div className="pq-preview-main"><div className="pq-preview-toolbar"><span>ENQUIRIES / <bdi>PQ-001</bdi></span><span className="pq-badge">Illustrative preview</span></div><div className="pq-preview-title"><div><span className="pq-eyebrow">PARTS ENQUIRY</span><h3>A clearer path to the right part.</h3></div><a href="/demo/mixed_photo" className="pq-icon-link" aria-label="Open example enquiry"><ArrowUpRight /></a></div><div className="pq-preview-panels"><div><span className="pq-eyebrow">01 / CUSTOMER REQUEST</span><p className="pq-message">“I need an air filter for my CA-110. Can you check the fit?”</p><div className="pq-file"><ScanLine size={24} /><div>Nameplate identification<small>Machine details, ready to review</small></div></div></div><div className="pq-preview-result"><span className="pq-eyebrow">02 / THE REVIEW PICTURE</span><h4>Air filter element</h4><p className="pq-muted"><bdi>CA-AF-8973</bdi> · Synthetic catalogue</p><div className="pq-check-row"><ShieldCheck size={16} /> Compatibility evidence</div><div className="pq-check-row"><PackageCheck size={16} /> Warehouse fulfilment plan</div><div className="pq-review-state">Human review required <span>→</span></div></div></div><a href="/demo/scenarios" className="pq-preview-bottom">Explore the guided scenarios <ArrowRight size={16} /></a></div>
        </div></Reveal>
      </section>
      <section className="pq-container pq-section pq-journey-section"><Reveal><div className="pq-section-heading"><div><span className="pq-eyebrow">02 / FROM QUESTION TO CONFIDENCE</span><h2>Complex behind the scenes.<br /><em>Clear at every step.</em></h2></div></div></Reveal><div className="pq-journey-grid">{JOURNEY.map((step, i) => <Reveal key={step.title} delay={i * 70}><article className="pq-journey-item"><div className="pq-step-top"><step.icon size={25} strokeWidth={1.4} /><span>0{i + 1}</span></div><h3>{step.title}</h3><p className="pq-muted">{step.text}</p></article></Reveal>)}</div></section>
      <section className="pq-trust-section"><div className="pq-container pq-trust-grid"><Reveal><span className="pq-eyebrow">03 / INTELLIGENCE WITH ACCOUNTABILITY</span><h2>Not just an answer.<br /><em>A reason to trust it.</em></h2><p>AI helps interpret the question. Explicit checks verify the facts. People make the final call.</p><a href="/architecture" className="pq-text-link">See how it is built <ArrowUpRight size={16} /></a></Reveal><div className="pq-trust-list">{[{title:"Evidence, not assumptions.",text:"Version-specific catalogue references keep recommendations traceable.",icon:FileCheck2},{title:"A checkpoint before every reply.",text:"Compatibility, quantities, and allocation are checked in code.",icon:ShieldCheck},{title:"Your reviewer. Your decision.",text:"Drafts stay drafts until a human approves the current revision.",icon:Fingerprint}].map(f => <Reveal key={f.title}><div className="pq-trust-item"><f.icon size={25} strokeWidth={1.3} /><div><h3>{f.title}</h3><p>{f.text}</p></div></div></Reveal>)}</div></div></section>
      <section className="pq-container pq-final-cta"><span className="pq-eyebrow">EXPLORE THE POSSIBILITIES</span><h2>Take a closer <em>look.</em></h2><p className="pq-muted">Four synthetic scenarios. One thoughtful workflow.<br />Try a photo enquiry, a missing serial, an incompatible part, or a stock shortage.</p><a href="/demo" className="pq-btn pq-btn-primary">Try the demo <ArrowUpRight size={17} /></a>{process.env.NEXT_PUBLIC_REPO_URL ? <a className="pq-text-link" href={process.env.NEXT_PUBLIC_REPO_URL}>Source code <ArrowUpRight size={16} /></a> : null}</section>
    </div>
  );
}
