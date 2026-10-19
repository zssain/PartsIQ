import { type JSX } from "react";

import { Reveal } from "@/components/ui/Reveal";
import { LiveDemo } from "@/components/live/LiveDemo";

// LIVE demo journey. One anonymous session (F04) wired to the fixture backend: submit an enquiry as
// the customer, watch the real persisted progress, then switch to the Reviewer view (F03) to see
// this session's own review queue, open it, and approve/reject — the published reply then appears
// back in the customer view. The redesigned look is preserved (same container/eyebrow/heading).
export default function LiveDemoPage(): JSX.Element {
  return (
    <div className="pq-container" style={{ paddingTop: 40, paddingBottom: 48 }}>
      <Reveal className="pq-page-top">
        <span className="pq-badge" style={{ marginBottom: 14 }}>THE WORKSPACE / LIVE FIXTURE</span>
        <h1 style={{ fontSize: "clamp(1.8rem, 4vw, 2.8rem)", fontWeight: 800 }}>
          One session, both seats.<br /><span className="pq-gradient-text">Submit, review, approve.</span>
        </h1>
        <p className="pq-muted" style={{ maxWidth: 640, marginTop: 12 }}>
          A single anonymous session talks to the fixture backend. Submit an enquiry as the customer,
          watch the real pipeline progress, then switch seats to the reviewer — you see only this
          session&rsquo;s own enquiries — and approve or reject. Synthetic data; no live providers.
        </p>
        <p style={{ marginTop: 14 }}>
          <a href="/demo" className="pq-text-link">← Back to the scenario walkthroughs</a>
        </p>
      </Reveal>

      <div style={{ marginTop: 28 }}>
        <LiveDemo />
      </div>
    </div>
  );
}
