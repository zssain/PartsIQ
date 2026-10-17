"use client";

import { useRouter } from "next/navigation";
import { useState, type JSX } from "react";

import { BrandLogo } from "@/components/BrandLogo";
import { startAnonymousDemo } from "@/lib/auth";

const JOURNEY = [
  "Send your parts enquiry in English or Arabic — type it or attach a nameplate photo (we check the photo is readable before sending).",
  "PartsIQ identifies the machine and retrieves only catalogue-compatible parts — ask for several parts in one message and each is tracked on its own.",
  "It plans warehouse fulfilment and drafts a bilingual reply.",
  "A human reviewer must approve before anything is published to you.",
];

// Optional repository link: the action is hidden entirely when the URL is not configured.
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
      setError("Could not start the demo. Please try again.");
      setBusy(false);
    }
  }

  return (
    <main>
      <header style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <BrandLogo />
      </header>

      <p role="note" data-testid="synthetic-notice" style={{ background: "#fff7ed", padding: 8, borderRadius: 6 }}>
        This is an independent, synthetic demonstration. All data is fabricated; it is not
        affiliated with any real distributor and makes no accuracy or delivery guarantee.
      </p>

      <h1>From enquiry to approved parts reply</h1>
      <ol>
        {JOURNEY.map((step) => (
          <li key={step}>{step}</li>
        ))}
      </ol>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <button type="button" onClick={onStartDemo} disabled={busy}>
          {busy ? "Starting…" : "Start demo"}
        </button>
        <a href="/architecture">How it works (architecture)</a>
        <a href="/history">Your enquiries</a>
        {REPO_URL ? <a href={REPO_URL}>Source code</a> : null}
      </div>

      {error ? <p role="alert">{error}</p> : null}
    </main>
  );
}
