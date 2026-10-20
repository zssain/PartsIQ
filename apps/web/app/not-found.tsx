import Link from "next/link";
import { type JSX } from "react";

export default function NotFound(): JSX.Element {
  return (
    <div className="pq-container" style={{ paddingTop: 80, paddingBottom: 80, textAlign: "center" }}>
      <div className="pq-gradient-text" style={{ fontSize: "5rem", fontWeight: 800, lineHeight: 1 }}>404</div>
      <h1 style={{ fontSize: "1.6rem", fontWeight: 800, marginTop: 10 }}>This page could not be found</h1>
      <p className="pq-muted" style={{ marginTop: 10 }}>The link may be stale, or the resource is out of your scope.</p>
      <div style={{ display: "flex", gap: 12, justifyContent: "center", marginTop: 24, flexWrap: "wrap" }}>
        <Link href="/" className="pq-btn pq-btn-primary">Back home</Link>
        <Link href="/demo" className="pq-btn pq-btn-ghost">Open the demo</Link>
      </div>
    </div>
  );
}
