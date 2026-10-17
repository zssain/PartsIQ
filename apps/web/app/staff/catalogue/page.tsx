import { type JSX } from "react";

import { TiltCard } from "@/components/ui/TiltCard";
import { Reveal } from "@/components/ui/Reveal";
import { SEED } from "@/lib/demo/engine";

// Offline catalogue browser (F57 shell). Shows a slice of the active published synthetic catalogue;
// in production this is cursor-paginated, filterable and served (published rows only) by the gateway.
export default function StaffCataloguePage(): JSX.Element {
  const parts = [
    { ...SEED.air_filter, fits: `${SEED.model.model_code} (A/B)`, citation: SEED.compatibility[0]?.source_reference ?? "" },
    { ...SEED.incompatible, fits: "frame S platforms (not CA-110)", citation: "" },
  ];
  return (
    <div className="pq-container" style={{ paddingTop: 40, paddingBottom: 40 }}>
      <Reveal>
        <span className="pq-badge" style={{ marginBottom: 12 }}>Staff · catalogue · offline</span>
        <h1 style={{ fontSize: "clamp(1.7rem, 4vw, 2.6rem)", fontWeight: 800 }}>Published catalogue</h1>
        <p className="pq-muted" style={{ marginTop: 10 }}>Only published-version rows are shown — never unpublished import-staging rows.</p>
      </Reveal>

      <div style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", marginTop: 24 }}>
        {parts.map((p, i) => (
          <Reveal key={p.part_number} delay={i * 80}>
            <TiltCard style={{ padding: 20, height: "100%" }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
                <strong style={{ fontFamily: "monospace" }}><bdi>{p.part_number}</bdi></strong>
                <span className="pq-chip">{p.category}</span>
              </div>
              <h2 style={{ fontSize: "1.1rem", fontWeight: 700, margin: "8px 0" }}>{p.name_en} / <bdi>{p.name_ar}</bdi></h2>
              <p className="pq-muted" style={{ fontSize: "0.88rem" }}>{p.description_en}</p>
              <div className="pq-chip" style={{ marginTop: 10 }}>fits: {p.fits}</div>
              {p.citation ? <div className="pq-chip" style={{ marginTop: 8 }}>📄 {p.citation}</div> : null}
            </TiltCard>
          </Reveal>
        ))}
      </div>
    </div>
  );
}
