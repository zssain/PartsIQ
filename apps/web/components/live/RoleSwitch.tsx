"use client";

import { type JSX } from "react";

// F03 role switch — a PRESENTATIONAL toggle between the Customer view and the Reviewer view of the
// SAME anonymous demo session (one X-Demo-Token throughout). Switching never changes identity or
// grants a staff role; it only changes which view of this session's own data is shown. Rendered as
// an accessible radio-style tablist so a keyboard/AT user can move between the two roles.
export type Role = "customer" | "reviewer";

export function RoleSwitch({
  role,
  onChange,
}: {
  role: Role;
  onChange: (next: Role) => void;
}): JSX.Element {
  return (
    <div
      role="tablist"
      aria-label="Demo role"
      data-testid="role-switch"
      style={{ display: "inline-flex", gap: 4, padding: 4, borderRadius: 999, background: "var(--pq-glass, rgba(255,255,255,0.06))" }}
    >
      {(["customer", "reviewer"] as const).map((r) => {
        const active = role === r;
        return (
          <button
            key={r}
            type="button"
            role="tab"
            aria-selected={active}
            aria-current={active ? "true" : undefined}
            data-testid={`role-${r}`}
            onClick={() => onChange(r)}
            className={active ? "pq-btn pq-btn-primary" : "pq-btn pq-btn-ghost"}
            style={{ padding: "0.45rem 1rem", borderRadius: 999 }}
          >
            {r === "customer" ? "Customer" : "Reviewer"}
          </button>
        );
      })}
    </div>
  );
}
