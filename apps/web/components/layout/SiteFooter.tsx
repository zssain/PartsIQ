import { type JSX } from "react";

// Site footer: synthetic-data reminder + quick links. Honest framing, no affiliation claim.
export function SiteFooter(): JSX.Element {
  return (
    <footer style={{ borderTop: "1px solid var(--pq-glass-border)", marginTop: 80 }}>
      <div
        className="pq-container"
        style={{ display: "flex", flexWrap: "wrap", gap: 16, justifyContent: "space-between", padding: "28px 20px", color: "var(--pq-muted)", fontSize: "0.86rem" }}
      >
        <span>
          © PartsIQ — an independent, synthetic demonstration. All data is fabricated; not affiliated with any
          distributor. The LLM reads/writes language; code and the database decide facts.
        </span>
        <span style={{ display: "flex", gap: 14 }}>
          <a href="/architecture">Architecture</a>
          <a href="/demo">Demo</a>
          <a href="/staff/inbox">Staff</a>
        </span>
      </div>
    </footer>
  );
}
