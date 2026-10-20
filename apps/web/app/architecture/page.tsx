import Link from "next/link";
import { type JSX } from "react";

import { TiltCard } from "@/components/ui/TiltCard";
import { Reveal } from "@/components/ui/Reveal";

const PIPELINE = [
  { k: "Intake", d: "Parse the enquiry; extract items, language, urgency." },
  { k: "Identify", d: "Resolve the machine + configuration from text/serial/photo." },
  { k: "Search", d: "Retrieve ONLY catalogue-compatible parts (lexical + BGE-M3)." },
  { k: "Choose", d: "Rank candidates; bounded, read-only specialist tools." },
  { k: "Plan", d: "Allocate across warehouses; show shortfalls honestly." },
  { k: "Draft", d: "Model writes prose slots; code inserts every fact." },
  { k: "Verify", d: "Seven named code checks decide pass/fail." },
  { k: "Review", d: "A human approves the current revision before publish." },
];

const SERVICES = [
  { icon: "🛡️", name: "gateway", tag: "FastAPI · public", d: "The only public surface. Verifies the Supabase token, enforces roles/assignment, calls use cases. Never runs heavy work inline." },
  { icon: "🔎", name: "search", tag: "domain · read-only", d: "Preserved legacy identification + compatible-set filtering + fulfilment planning, plus BGE-M3 semantic retrieval." },
  { icon: "🧠", name: "orchestrator", tag: "LangGraph · durable", d: "The workflow + the deterministic verification gate + approval/revision transactions. Pass/fail decided in code." },
  { icon: "⚙️", name: "worker", tag: "jobs · fenced", d: "Nameplate OCR, approved-PDF export, catalogue import/publish — behind leases with fencing tokens." },
  { icon: "💻", name: "apps/web", tag: "Next.js 16 · React 19", d: "Customer chat + demo, staff review workspace; bilingual (en/ar), theming, responsive." },
];

const CHECKS = ["current_revision", "catalogue_version", "candidate_membership", "configuration_membership", "source_evidence", "quantity", "allocation"];

export default function ArchitecturePage(): JSX.Element {
  return (
    <div className="pq-container" style={{ paddingTop: 40, paddingBottom: 48 }}>
      <Reveal className="pq-page-top">
        <span className="pq-badge" style={{ marginBottom: 14 }}>System design</span>
        <h1 style={{ fontSize: "clamp(1.9rem, 4.5vw, 3rem)", fontWeight: 800 }}>
          How <span className="pq-gradient-text">PartsIQ</span> works
        </h1>
        <p className="pq-muted" style={{ maxWidth: 680, marginTop: 12 }}>
          A durable, auditable pipeline. The language model reads and writes natural language; the database and code
          decide every fact — compatibility, stock, quantity and approval.
        </p>
      </Reveal>

      {/* Pipeline */}
      <section style={{ marginTop: 40 }}>
        <Reveal><h2 style={{ fontSize: "1.5rem", fontWeight: 800, marginBottom: 18 }}>The request pipeline</h2></Reveal>
        <div style={{ display: "grid", gap: 14, gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))" }}>
          {PIPELINE.map((p, i) => (
            <Reveal key={p.k} delay={i * 60}>
              <TiltCard style={{ padding: 16, height: "100%" }} max={7}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span className="pq-chip" style={{ border: "none", background: "var(--pq-grad-brand)", color: "#1a1405" }}>{i + 1}</span>
                  <strong>{p.k}</strong>
                </div>
                <p className="pq-muted" style={{ fontSize: "0.86rem", marginTop: 8 }}>{p.d}</p>
              </TiltCard>
            </Reveal>
          ))}
        </div>
      </section>

      {/* Services */}
      <section style={{ marginTop: 56 }}>
        <Reveal><h2 style={{ fontSize: "1.5rem", fontWeight: 800, marginBottom: 18 }}>Services</h2></Reveal>
        <div style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))" }}>
          {SERVICES.map((s, i) => (
            <Reveal key={s.name} delay={i * 70}>
              <TiltCard style={{ padding: 20, height: "100%" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: "1.6rem" }} aria-hidden="true">{s.icon}</span>
                  <span className="pq-chip">{s.tag}</span>
                </div>
                <h3 style={{ fontFamily: "monospace", fontSize: "1.1rem", fontWeight: 700, margin: "10px 0 8px" }}>{s.name}</h3>
                <p className="pq-muted" style={{ fontSize: "0.9rem" }}>{s.d}</p>
              </TiltCard>
            </Reveal>
          ))}
        </div>
      </section>

      {/* Determinism callout */}
      <Reveal>
        <section className="pq-card" style={{ marginTop: 56, padding: "28px 24px" }}>
          <h2 style={{ fontSize: "1.4rem", fontWeight: 800 }}>Deterministic verification gate</h2>
          <p className="pq-muted" style={{ maxWidth: 680, marginTop: 10 }}>
            Before a recommendation can reach a human, it must pass seven named, pure code checks. An LLM is never
            asked whether verification passed; a failed check surfaces to the reviewer, never silently treated as success.
          </p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 16 }}>
            {CHECKS.map((c) => (
              <span key={c} className="pq-chip" style={{ fontFamily: "monospace" }}>{c} ✓</span>
            ))}
          </div>
        </section>
      </Reveal>

      <Reveal>
        <div style={{ display: "flex", gap: 12, marginTop: 40, flexWrap: "wrap" }}>
          <Link href="/demo" className="pq-btn pq-btn-primary">See it run on four scenarios →</Link>
          <Link href="/" className="pq-btn pq-btn-ghost">Back home</Link>
        </div>
      </Reveal>
    </div>
  );
}
