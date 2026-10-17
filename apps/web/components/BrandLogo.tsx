import type { JSX } from "react";

// The supplied PartsIQ logo. Rendered at a fixed height with width auto and object-contain
// so it never stretches (F01); alt text is meaningful for screen readers. `compact` is used
// in dense headers. No affiliation is claimed — this is an independent synthetic project.
export function BrandLogo({ compact = false }: { compact?: boolean }): JSX.Element {
  const height = compact ? 28 : 44;
  return (
    <img
      src="/brand/assets/PartsIQ-Asset-Pack/logos/partsiq-logo-transparent-640.png"
      alt="PartsIQ — independent synthetic demonstration"
      className="pq-brand-logo"
      height={height}
      style={{ height, width: "auto", objectFit: "contain", display: "block" }}
    />
  );
}
