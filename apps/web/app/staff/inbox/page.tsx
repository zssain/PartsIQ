import { type JSX } from "react";

import { TiltCard } from "@/components/ui/TiltCard";
import { Reveal } from "@/components/ui/Reveal";
import { SCENARIOS } from "@/lib/demo/engine";

// Offline staff inbox (F36 shell). With no backend it lists the four synthetic scenarios as
// review items — each opens the guided review + approval flow. In production this is the
// assignment-scoped, filterable enquiry list served by the gateway.
const META: Record<string, { status: string; priority: "normal" | "urgent"; overdue: boolean }> = {
  mixed_photo: { status: "awaiting_review", priority: "normal", overdue: false },
  missing_serial: { status: "needs_information", priority: "normal", overdue: false },
  incompatible_number: { status: "needs_information", priority: "normal", overdue: false },
  local_shortage: { status: "awaiting_review", priority: "urgent", overdue: true },
};

const STATUS_COLOR: Record<string, string> = {
  awaiting_review: "var(--pq-gold)",
  needs_information: "var(--pq-cyan)",
  approved: "var(--pq-teal)",
};

export default function InboxPage(): JSX.Element {
  const scoped = SCENARIOS.length;
  return (
    <div className="pq-container" style={{ paddingTop: 40, paddingBottom: 40 }}>
      <Reveal className="pq-page-top">
        <span className="pq-badge" style={{ marginBottom: 12 }}>Staff · offline synthetic</span>
        <h1 style={{ fontSize: "clamp(1.7rem, 4vw, 2.6rem)", fontWeight: 800 }}>Review inbox</h1>
        <p className="pq-muted" style={{ marginTop: 10 }}>
          {scoped} enquiries in your scope. Assignment scoping, filters and counts are enforced server-side;
          evaluation metrics are admin-only.
        </p>
      </Reveal>

      <div style={{ display: "grid", gap: 14, marginTop: 24 }}>
        {SCENARIOS.map((s, i) => {
          const m = META[s.id];
          return (
            <Reveal key={s.id} delay={i * 70}>
              <a href={`/demo/${s.id}`} style={{ display: "block" }}>
                <TiltCard style={{ padding: 18 }} max={5}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
                    <div>
                      <strong style={{ fontSize: "1.05rem" }}>
                        <span aria-hidden="true">{s.icon}</span> {s.title}
                      </strong>
                      <p className="pq-muted" style={{ fontSize: "0.88rem", marginTop: 4 }}>{s.blurb}</p>
                    </div>
                    <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                      {m.overdue ? <span className="pq-chip" style={{ border: "none", background: "var(--pq-pink)", color: "#0a1420" }}>overdue</span> : null}
                      {m.priority === "urgent" ? <span className="pq-chip">urgent</span> : null}
                      <span className="pq-chip" style={{ border: "none", background: STATUS_COLOR[m.status] ?? "var(--pq-glass)", color: "#0a1420" }}>
                        {m.status.replace("_", " ")}
                      </span>
                      <span className="pq-btn pq-btn-ghost" style={{ padding: "0.4rem 0.8rem" }}>Review →</span>
                    </div>
                  </div>
                </TiltCard>
              </a>
            </Reveal>
          );
        })}
      </div>

      <Reveal>
        <div style={{ marginTop: 32, display: "flex", gap: 12, flexWrap: "wrap" }}>
          <a href="/staff/analytics" className="pq-btn pq-btn-ghost">Analytics →</a>
          <a href="/staff/catalogue" className="pq-btn pq-btn-ghost">Catalogue →</a>
          <a href="/staff/imports" className="pq-btn pq-btn-ghost">Imports →</a>
        </div>
      </Reveal>
    </div>
  );
}
