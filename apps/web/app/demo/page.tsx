"use client";

import { useRouter } from "next/navigation";
import { useState, type JSX } from "react";

import { api, ApiError } from "@/lib/api";
import type { EnquiryView } from "@/lib/contracts";

// Demo home (F02, F05). Four deterministic scenario cards seed fresh enquiries on explicit
// selection; Reset locks the session, increments the generation server-side, and clears the
// client cache so stale/old-generation data cannot reappear. Scenario identifiers are seed-42
// derived server-side — the client only names the scenario to start.
const SCENARIOS = [
  { id: "mixed_photo", title: "Mixed-language photo", blurb: "Arabic/English text plus a nameplate photo." },
  { id: "missing_serial", title: "Missing serial", blurb: "The machine serial is not provided yet." },
  { id: "incompatible_number", title: "Incompatible part number", blurb: "A quoted part that does not fit." },
  { id: "local_shortage", title: "Local shortage", blurb: "Stock must transfer from another warehouse." },
] as const;

export default function DemoPage(): JSX.Element {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function startScenario(scenarioId: string) {
    setBusy(scenarioId);
    setError(null);
    try {
      const enquiry = await api<EnquiryView>("/v1/demo/scenarios", {
        method: "POST",
        headers: { "idempotency-key": crypto.randomUUID() },
        body: JSON.stringify({ scenario: scenarioId }),
      });
      router.push(`/chat/${enquiry.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not start that scenario.");
      setBusy(null);
    }
  }

  async function reset() {
    setError(null);
    try {
      await api("/v1/demo/reset", { method: "POST", headers: { "idempotency-key": crypto.randomUUID() } });
      // Clear any client-held enquiry cache so old-generation data cannot resurface.
      if (typeof window !== "undefined") window.sessionStorage.clear();
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Reset failed.");
    }
  }

  return (
    <main>
      <h1>Try a demo scenario</h1>
      <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
        {SCENARIOS.map((s) => (
          <button key={s.id} type="button" onClick={() => startScenario(s.id)} disabled={busy !== null} data-testid={`scenario-${s.id}`}>
            <strong>{s.title}</strong>
            <span>{s.blurb}</span>
          </button>
        ))}
      </div>
      <button type="button" onClick={reset} data-testid="demo-reset">
        Reset demo
      </button>
      {error ? <p role="alert">{error}</p> : null}
    </main>
  );
}
