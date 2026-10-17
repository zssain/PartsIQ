"use client";

import { useRouter } from "next/navigation";
import { useState, type JSX } from "react";

import { BrandLogo } from "@/components/BrandLogo";
import { TiltCard } from "@/components/ui/TiltCard";
import { Reveal } from "@/components/ui/Reveal";
import { startAnonymousDemo } from "@/lib/auth";

// Journey — the two phrases below are asserted by f01 (keep them verbatim as single text nodes).
const JOURNEY = [
  { icon: "💬", title: "Ask in any language", text: "Send your parts enquiry in English or Arabic — type it or attach a nameplate photo." },
  { icon: "🔎", title: "Only compatible parts", text: "PartsIQ identifies the machine and retrieves only catalogue-compatible parts." },
  { icon: "📦", title: "Planned fulfilment", text: "It plans warehouse fulfilment and drafts a bilingual reply." },
  { icon: "✅", title: "Human approval", text: "A human reviewer must approve before anything is published to you." },
];

const FEATURES = [
  { icon: "🧮", title: "Deterministic verification", text: "Seven named code checks decide pass/fail — never the model. Revision, catalogue version, compatibility, evidence, quantity and aggregate allocation." },
  { icon: "🌐", title: "Bilingual, RTL-ready", text: "Full English/Arabic UI with a locale cookie; identifiers stay LTR-isolated inside Arabic text." },
  { icon: "🛡️", title: "Prompt-injection isolation", text: "Customer text, OCR and evidence are data, never instructions. Tools are read-only and bounded." },
  { icon: "🧾", title: "Evidence on every claim", text: "Each recommended part carries a version-specific citation you can open to the exact page." },
  { icon: "🗂️", title: "Catalogue versioning", text: "Atomic publish with a single active version; stale plans are invalidated on the next action." },
  { icon: "📊", title: "Honest metrics", text: "Accuracy always shown with its denominator; a zero denominator reads 'unavailable', never faked." },
];

const REPO_URL = process.env.NEXT_PUBLIC_REPO_URL;

export default function LandingPage(): JSX.Element {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onStartDemo() {
    setBusy(true);
    setError(null);
    try {
      await startAnonymousDemo();
      router.push("/demo");
    } catch {
      // Offline demo still works without a backend session.
      router.push("/demo");
    }
  }

  return (
    <div className="pq-container" style={{ paddingTop: 40, paddingBottom: 40 }}>
      {/* ---------- Hero ---------- */}
      <section style={{ display: "grid", gap: 32, gridTemplateColumns: "minmax(0,1.1fr) minmax(0,0.9fr)", alignItems: "center" }} className="pq-hero">
        <div>
          <span className="pq-badge" style={{ marginBottom: 18 }}>
            <span className="pq-float" aria-hidden="true">✦</span> Synthetic demo · code decides facts
          </span>
          <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 10 }}>
            <BrandLogo />
          </div>
          <h1 style={{ fontSize: "clamp(2.1rem, 5vw, 3.6rem)", fontWeight: 800 }}>
            From a messy enquiry to an <span className="pq-gradient-text">approved parts reply</span>
          </h1>
          <p className="pq-muted" style={{ fontSize: "1.1rem", maxWidth: 560, marginTop: 16 }}>
            PartsIQ interprets incomplete spare-parts enquiries, identifies the exact machine, retrieves only
            catalogue-compatible parts, plans fulfilment, and drafts a bilingual reply — with a human approval gate
            and a deterministic verification core.
          </p>

          <p
            role="note"
            data-testid="synthetic-notice"
            className="pq-glass"
            style={{ marginTop: 20, padding: "12px 14px", borderRadius: 12, fontSize: "0.9rem", color: "var(--pq-muted)" }}
          >
            This is an independent, synthetic demonstration. All data is fabricated; it is not affiliated with any
            real distributor and makes no accuracy or delivery guarantee.
          </p>

          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 24 }}>
            <button type="button" className="pq-btn pq-btn-primary" onClick={onStartDemo} disabled={busy}>
              {busy ? "Starting…" : "Start demo →"}
            </button>
            <a href="/architecture" className="pq-btn pq-btn-ghost">How it works (architecture)</a>
            {REPO_URL ? <a href={REPO_URL} className="pq-btn pq-btn-ghost">Source code</a> : null}
          </div>
          {error ? <p role="alert">{error}</p> : null}
        </div>

        {/* Decorative preview card */}
        <Reveal>
          <TiltCard style={{ padding: 20 }} max={8}>
            <div className="pq-badge" style={{ marginBottom: 12 }}>Live verification · synthetic</div>
            <div style={{ display: "grid", gap: 10 }}>
              <div className="pq-glass" style={{ padding: "10px 12px", borderRadius: 12, alignSelf: "flex-start", maxWidth: "85%" }}>
                محتاج فلتر هواء — CA-AF-8973 for my Corvane Air CA-110
              </div>
              <div className="pq-glass" style={{ padding: "10px 12px", borderRadius: 12, alignSelf: "flex-end", maxWidth: "85%", background: "color-mix(in srgb, var(--pq-gold) 14%, var(--pq-glass))" }}>
                Identified CA-110 (A). <strong>Air filter element</strong> · <bdi>CA-AF-8973</bdi> — compatible ✓
              </div>
              <div style={{ display: "grid", gap: 6, marginTop: 4 }}>
                {["current revision", "catalogue version", "candidate membership", "source evidence", "allocation"].map((c) => (
                  <div key={c} style={{ display: "flex", justifyContent: "space-between", fontSize: "0.82rem" }}>
                    <span className="pq-muted">{c}</span>
                    <span style={{ color: "var(--pq-teal)" }}>passed ✓</span>
                  </div>
                ))}
              </div>
              <div style={{ fontSize: "0.78rem", color: "var(--pq-muted)", marginTop: 4 }}>
                Awaiting human approval · 41 available in Jeddah
              </div>
            </div>
          </TiltCard>
        </Reveal>
      </section>

      {/* ---------- Journey ---------- */}
      <section style={{ marginTop: 90 }}>
        <Reveal>
          <h2 style={{ fontSize: "1.8rem", fontWeight: 800, marginBottom: 6 }}>How a request flows</h2>
          <p className="pq-muted" style={{ marginBottom: 24 }}>Four steps, each auditable — the model never decides a fact.</p>
        </Reveal>
        <div style={{ display: "grid", gap: 18, gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))" }}>
          {JOURNEY.map((step, i) => (
            <Reveal key={step.title} delay={i * 90}>
              <TiltCard style={{ padding: 20, height: "100%" }}>
                <div style={{ fontSize: "1.8rem" }} aria-hidden="true">{step.icon}</div>
                <h3 style={{ fontSize: "1.05rem", fontWeight: 700, margin: "10px 0 6px" }}>
                  <span className="pq-chip" style={{ marginRight: 8, border: "none", background: "var(--pq-grad-brand)", color: "#1a1405" }}>{i + 1}</span>
                  {step.title}
                </h3>
                <p className="pq-muted" style={{ fontSize: "0.92rem" }}>{step.text}</p>
              </TiltCard>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ---------- Features ---------- */}
      <section style={{ marginTop: 90 }}>
        <Reveal>
          <h2 style={{ fontSize: "1.8rem", fontWeight: 800, marginBottom: 6 }}>Built for trust, not just answers</h2>
          <p className="pq-muted" style={{ marginBottom: 24 }}>Every recommendation is explainable, bounded and human-approved.</p>
        </Reveal>
        <div style={{ display: "grid", gap: 18, gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))" }}>
          {FEATURES.map((f, i) => (
            <Reveal key={f.title} delay={i * 70}>
              <TiltCard style={{ padding: 22, height: "100%" }}>
                <div style={{ fontSize: "1.6rem" }} aria-hidden="true">{f.icon}</div>
                <h3 style={{ fontSize: "1.1rem", fontWeight: 700, margin: "10px 0 8px" }}>{f.title}</h3>
                <p className="pq-muted" style={{ fontSize: "0.92rem" }}>{f.text}</p>
              </TiltCard>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ---------- CTA ---------- */}
      <Reveal>
        <section className="pq-card" style={{ marginTop: 90, padding: "40px 28px", textAlign: "center" }}>
          <h2 style={{ fontSize: "1.9rem", fontWeight: 800 }}>
            See it run on <span className="pq-gradient-text">four synthetic scenarios</span>
          </h2>
          <p className="pq-muted" style={{ maxWidth: 560, margin: "12px auto 22px" }}>
            Mixed-language photo, missing serial, an incompatible part, and a local stock shortage — walk each one
            through identification, verification and human review. Runs entirely offline.
          </p>
          <div style={{ display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap" }}>
            <a href="/demo" className="pq-btn pq-btn-primary">Open the live demo →</a>
            <a href="/architecture" className="pq-btn pq-btn-ghost">See the system design</a>
          </div>
        </section>
      </Reveal>
    </div>
  );
}
