"use client";

import { useEffect, useState, type JSX, type ReactNode } from "react";

import type { ApiError } from "@/lib/api";
import { get_layout, type F06Request, type F06Result } from "@/lib/features/f06_responsive_layouts";

// F06 Responsive shell — lays children out in 1/2/3 columns for the 360/768/1280 targets and
// re-measures on resize. Review panels stack on mobile; the page never scrolls horizontally
// (tokens.css). Wide content goes in a `.pq-scroll-x` region so only that region scrolls. A
// controlled `value` overrides the measurement (used in tests). Submits only typed measurements.
export function ResponsiveShell(props: {
  value: F06Result | null;
  loading: boolean;
  error: ApiError | null;
  onAction: (request: F06Request) => Promise<void>;
  children?: ReactNode;
}): JSX.Element {
  const { value, loading, error, onAction, children } = props;
  const [measured, setMeasured] = useState<F06Result | null>(value);

  useEffect(() => {
    if (value) return; // controlled: skip measurement
    function measure() {
      const width = typeof window !== "undefined" ? window.innerWidth : 1280;
      let reducedMotion = false;
      try {
        reducedMotion = !!window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
      } catch {
        reducedMotion = false;
      }
      setMeasured(get_layout({ width, reducedMotion }));
      void onAction({ width, reducedMotion });
    }
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [value, onAction]);

  const effective = value ?? measured;
  const columns = effective?.columns ?? 1;

  return (
    <div
      data-testid="responsive-shell"
      data-columns={columns}
      data-compact={effective?.compact ?? true}
      style={{ display: "grid", gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`, gap: 16, maxWidth: "100%" }}
    >
      {loading ? <p data-testid="shell-loading">Loading…</p> : null}
      {error ? <p role="alert">{error.message}</p> : null}
      {children}
    </div>
  );
}
