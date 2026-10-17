"use client";

import { useMemo, useState, type JSX } from "react";

import { TiltCard } from "@/components/ui/TiltCard";
import type { Scenario } from "@/lib/demo/engine";

// Fully offline, interactive walkthrough of one synthetic scenario. Steps are revealed as the
// reviewer advances; the final step is the human approval gate. No backend — facts come from the
// seed-42 engine. Nothing is "published" until a human clicks Approve.
type StepKey = "enquiry" | "identify" | "ocr" | "candidates" | "fulfilment" | "verify" | "reply" | "review";

export function DemoWalkthrough({ scenario }: { scenario: Scenario }): JSX.Element {
  const steps = useMemo<{ key: StepKey; label: string }[]>(() => {
    const s: { key: StepKey; label: string }[] = [
      { key: "enquiry", label: "Enquiry" },
      { key: "identify", label: "Identify machine" },
    ];
    if (scenario.needsOcr) s.push({ key: "ocr", label: "Confirm nameplate" });
    s.push({ key: "candidates", label: "Candidates" });
    if (scenario.plan) s.push({ key: "fulfilment", label: "Fulfilment" });
    s.push({ key: "verify", label: "Verification" });
    s.push({ key: scenario.reply ? "reply" : "candidates", label: scenario.reply ? "Draft reply" : "Clarify" });
    if (scenario.outcome === "awaiting_review" && scenario.reply) s.push({ key: "review", label: "Human review" });
    return s;
  }, [scenario]);

  const [cursor, setCursor] = useState(0);
  const [lang, setLang] = useState<"en" | "ar">("en");
  const [decision, setDecision] = useState<"published" | "rejected" | null>(null);

  const active = steps[cursor]?.key;
  const atEnd = cursor >= steps.length - 1;

  return (
    <div style={{ display: "grid", gap: 20, gridTemplateColumns: "minmax(0, 220px) minmax(0, 1fr)" }} className="pq-wt">
      {/* Progress rail */}
      <aside>
        <div className="pq-card" style={{ padding: 16, position: "sticky", top: 84 }}>
          <div className="pq-badge" style={{ marginBottom: 12 }}>
            <span aria-hidden="true">{scenario.icon}</span> {scenario.title}
          </div>
          <ol style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 10 }}>
            {steps.map((st, i) => {
              const state = i < cursor ? "done" : i === cursor ? "active" : "pending";
              return (
                <li key={st.key + i} style={{ display: "flex", alignItems: "center", gap: 10, opacity: state === "pending" ? 0.5 : 1 }}>
                  <span
                    aria-hidden="true"
                    style={{
                      width: 24, height: 24, borderRadius: 999, display: "grid", placeItems: "center", fontSize: 12, fontWeight: 700,
                      background: state === "done" ? "var(--pq-teal)" : state === "active" ? "var(--pq-grad-brand)" : "var(--pq-glass)",
                      color: state === "pending" ? "var(--pq-muted)" : "#0a1420",
                      border: "1px solid var(--pq-glass-border)",
                    }}
                  >
                    {state === "done" ? "✓" : i + 1}
                  </span>
                  <span style={{ fontSize: "0.9rem", fontWeight: state === "active" ? 700 : 500 }}>{st.label}</span>
                </li>
              );
            })}
          </ol>
        </div>
      </aside>

      {/* Stage content (reveals cumulatively) */}
      <div style={{ display: "grid", gap: 16 }}>
        {steps.slice(0, cursor + 1).map((st, i) => (
          <StageCard key={st.key + i} active={i === cursor}>
            {renderStage(st.key, scenario, { lang, setLang })}
          </StageCard>
        ))}

        {active === "review" ? (
          <div className="pq-card pq-sticky-actions" style={{ padding: 16, display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
            {decision === null ? (
              <>
                <strong>Human approval required</strong>
                <span className="pq-muted" style={{ fontSize: "0.85rem" }}>Nothing is published until you approve.</span>
                <span style={{ flex: 1 }} />
                <button type="button" className="pq-btn pq-btn-ghost" onClick={() => setDecision("rejected")}>Reject</button>
                <button type="button" className="pq-btn pq-btn-primary" onClick={() => setDecision("published")}>Approve &amp; publish</button>
              </>
            ) : decision === "published" ? (
              <strong style={{ color: "var(--pq-teal)" }}>✓ Published — reply sent to the customer (synthetic).</strong>
            ) : (
              <strong style={{ color: "var(--pq-pink)" }}>✕ Rejected — returned for correction; nothing was published.</strong>
            )}
          </div>
        ) : (
          <div style={{ display: "flex", gap: 12 }}>
            <button type="button" className="pq-btn pq-btn-primary" onClick={() => setCursor((c) => Math.min(c + 1, steps.length - 1))} disabled={atEnd}>
              {atEnd ? "Walkthrough complete" : "Continue →"}
            </button>
            {cursor > 0 ? (
              <button type="button" className="pq-btn pq-btn-ghost" onClick={() => setCursor((c) => Math.max(0, c - 1))}>← Back</button>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
}

function StageCard({ children, active }: { children: React.ReactNode; active: boolean }): JSX.Element {
  return (
    <div className="pq-card" style={{ padding: 18, borderColor: active ? "color-mix(in srgb, var(--pq-gold) 45%, var(--pq-glass-border))" : undefined }}>
      {children}
    </div>
  );
}

function H({ children }: { children: React.ReactNode }) {
  return <h3 style={{ fontSize: "1.05rem", fontWeight: 700, marginBottom: 10 }}>{children}</h3>;
}

function renderStage(key: StepKey, s: Scenario, ui: { lang: "en" | "ar"; setLang: (l: "en" | "ar") => void }): JSX.Element {
  switch (key) {
    case "enquiry":
      return (
        <div>
          <H>Customer enquiry</H>
          <div style={{ display: "grid", gap: 8 }}>
            {s.chat.map((m, i) => (
              <div
                key={i}
                dir={m.lang === "ar" ? "rtl" : undefined}
                className="pq-glass"
                style={{
                  padding: "10px 12px", borderRadius: 12, maxWidth: "88%",
                  alignSelf: m.role === "customer" ? "flex-start" : "flex-end",
                  background: m.role === "system" ? "color-mix(in srgb, var(--pq-gold) 12%, var(--pq-glass))" : undefined,
                }}
              >
                {m.note ? <div className="pq-chip" style={{ marginBottom: 6, border: "none" }}>{m.note}</div> : null}
                {m.text}
              </div>
            ))}
          </div>
        </div>
      );
    case "identify":
      return (
        <div>
          <H>Machine identified</H>
          <p><strong>{s.machine.display_name}</strong>{s.machine.config ? ` · configuration ${s.machine.config}` : ""}</p>
          <p className="pq-muted" style={{ fontSize: "0.88rem" }}>
            {s.machine.config ? "Serial maps to a single configuration; retrieval is scoped to its compatible set." : "Configuration unknown — the system will ask rather than guess."}
          </p>
        </div>
      );
    case "ocr":
      return (
        <div>
          <H>Nameplate OCR — confirmation required</H>
          <p className="pq-muted" style={{ fontSize: "0.9rem" }}>Model and serial were read from the photo. Confirmation is always required (confidence is never treated as accuracy).</p>
          <div style={{ display: "flex", gap: 10, marginTop: 10, flexWrap: "wrap" }}>
            <span className="pq-chip">model: CA-110</span>
            <span className="pq-chip">serial: <bdi>800000</bdi></span>
            <span className="pq-chip" style={{ background: "var(--pq-teal)", color: "#0a1420", border: "none" }}>confirmed ✓</span>
          </div>
        </div>
      );
    case "candidates":
      return (
        <div>
          <H>{s.candidates.length ? "Candidate parts" : "No candidate yet"}</H>
          {s.candidates.length === 0 ? (
            <p className="pq-muted">{s.clarification}</p>
          ) : (
            <div style={{ display: "grid", gap: 10 }}>
              {s.candidates.map((c) => (
                <div key={c.part_number} className="pq-glass" style={{ padding: 12, borderRadius: 12, borderLeft: `3px solid ${c.compatible ? "var(--pq-teal)" : "var(--pq-pink)"}` }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
                    <strong><bdi>{c.part_number}</bdi> — {c.name_en} / <bdi>{c.name_ar}</bdi></strong>
                    <span className="pq-chip" style={{ border: "none", background: c.compatible ? "var(--pq-teal)" : "var(--pq-pink)", color: "#0a1420" }}>
                      {c.compatible ? "compatible ✓" : "not compatible ✕"}
                    </span>
                  </div>
                  <div className="pq-muted" style={{ fontSize: "0.85rem", marginTop: 4 }}>
                    {c.reason} · <span title="match score, not a probability">match score {c.score.toFixed(2)}</span>
                  </div>
                  {c.source_reference ? <div className="pq-chip" style={{ marginTop: 8 }} title="version-specific citation">📄 {c.source_reference}</div> : null}
                </div>
              ))}
            </div>
          )}
        </div>
      );
    case "fulfilment":
      return (
        <div>
          <H>Fulfilment plan</H>
          <div className="pq-scroll-x">
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
              <thead>
                <tr style={{ textAlign: "left", color: "var(--pq-muted)" }}>
                  <th style={{ padding: "6px 8px" }}>Warehouse</th>
                  <th style={{ padding: "6px 8px" }}>Allocated</th>
                  <th style={{ padding: "6px 8px" }}>Available</th>
                  <th style={{ padding: "6px 8px" }}>Transfer</th>
                </tr>
              </thead>
              <tbody>
                {s.plan!.allocations.map((a) => (
                  <tr key={a.warehouse} style={{ borderTop: "1px solid var(--pq-glass-border)" }}>
                    <td style={{ padding: "8px" }}>{a.name}</td>
                    <td style={{ padding: "8px" }}>{a.qty}</td>
                    <td style={{ padding: "8px" }}>{a.available}</td>
                    <td style={{ padding: "8px" }}>{a.transfer_days === 0 ? "in stock" : `${a.transfer_days}d (est.)`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p style={{ marginTop: 10 }}>
            Requested <strong>{s.plan!.requested}</strong> · allocated <strong>{s.plan!.allocations.reduce((n, a) => n + a.qty, 0)}</strong>
            {s.plan!.shortage > 0 ? <> · <span style={{ color: "var(--pq-pink)" }}>back-order {s.plan!.shortage}</span> (shown, not hidden)</> : <> · fully covered ✓</>}
          </p>
          <p className="pq-muted" style={{ fontSize: "0.82rem" }}>Transfer times are non-guaranteed estimates.</p>
        </div>
      );
    case "verify":
      return (
        <div>
          <H>Deterministic verification</H>
          <p className="pq-muted" style={{ fontSize: "0.85rem", marginBottom: 10 }}>Decided in code, never by the model.</p>
          <div style={{ display: "grid", gap: 6 }}>
            {s.checks.map((c) => (
              <div key={c.name} style={{ display: "flex", justifyContent: "space-between", gap: 10, padding: "6px 0", borderBottom: "1px solid var(--pq-glass-border)" }}>
                <span><code>{c.name}</code> <span className="pq-muted" style={{ fontSize: "0.82rem" }}>— {c.detail}</span></span>
                <span style={{ color: c.passed ? "var(--pq-teal)" : "var(--pq-pink)", fontWeight: 700, whiteSpace: "nowrap" }}>{c.passed ? "passed ✓" : "blocked ✕"}</span>
              </div>
            ))}
          </div>
          <p style={{ marginTop: 10, fontWeight: 700, color: s.checks.every((c) => c.passed) ? "var(--pq-teal)" : "var(--pq-pink)" }}>
            {s.checks.every((c) => c.passed) ? "All checks passed → ready for human review" : "Verification blocked → the system asks for more information"}
          </p>
        </div>
      );
    case "reply":
      if (!s.reply) return <div><H>Clarification</H><p className="pq-muted">{s.clarification}</p></div>;
      return (
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
            <H>Drafted reply (facts inserted by code)</H>
            <div className="pq-badge" role="group" aria-label="Reply language" style={{ padding: "0.2rem", gap: "0.1rem" }}>
              <button type="button" className="pq-chip" style={{ border: "none", background: ui.lang === "en" ? "var(--pq-grad-brand)" : "transparent", color: ui.lang === "en" ? "#1a1405" : "inherit" }} onClick={() => ui.setLang("en")}>EN</button>
              <button type="button" className="pq-chip" style={{ border: "none", background: ui.lang === "ar" ? "var(--pq-grad-brand)" : "transparent", color: ui.lang === "ar" ? "#1a1405" : "inherit" }} onClick={() => ui.setLang("ar")}>ع</button>
            </div>
          </div>
          <div dir={ui.lang === "ar" ? "rtl" : "ltr"} className="pq-glass" style={{ padding: 14, borderRadius: 12 }}>
            {ui.lang === "ar" ? s.reply.ar : s.reply.en}
          </div>
          <p className="pq-muted" style={{ fontSize: "0.8rem", marginTop: 8 }}>No price or quotation. Draft only — not sent until approved.</p>
        </div>
      );
    case "review":
    default:
      return <div><H>Ready for review</H><p className="pq-muted">Scroll to the approval bar below.</p></div>;
  }
}
