import Link from "next/link";
import { notFound } from "next/navigation";
import { type JSX } from "react";

import { DemoWalkthrough } from "@/components/demo/DemoWalkthrough";
import { SCENARIOS, getScenario } from "@/lib/demo/engine";

export function generateStaticParams() {
  return SCENARIOS.map((s) => ({ id: s.id }));
}

export default async function ScenarioPage({ params }: { params: Promise<{ id: string }> }): Promise<JSX.Element> {
  const { id } = await params;
  const scenario = getScenario(id);
  if (!scenario) notFound();

  return (
    <div className="pq-container" style={{ paddingTop: 32, paddingBottom: 48 }}>
      <Link href="/demo/scenarios" className="pq-chip" style={{ display: "inline-block", marginBottom: 16 }}>← All scenarios</Link>
      <h1 style={{ fontSize: "clamp(1.6rem, 3.5vw, 2.4rem)", fontWeight: 800, marginBottom: 6 }}>
        <span aria-hidden="true">{scenario.icon}</span> {scenario.title}
      </h1>
      <p className="pq-muted" style={{ marginBottom: 24, maxWidth: 640 }}>{scenario.blurb}</p>
      <DemoWalkthrough scenario={scenario} />
    </div>
  );
}
