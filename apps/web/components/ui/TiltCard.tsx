"use client";

import { useRef, type CSSProperties, type JSX, type ReactNode } from "react";

// 3D parallax tilt card. On pointer move it rotates toward the cursor and feeds --mx/--my to the
// oil sheen (tokens.css .pq-tilt::after). Reduced-motion users get a static card (no transform).
export function TiltCard({
  children,
  className = "",
  style,
  max = 10,
  as = "div",
}: {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
  max?: number;
  as?: "div" | "article" | "li";
}): JSX.Element {
  const ref = useRef<HTMLDivElement>(null);

  function onMove(e: React.PointerEvent) {
    const el = ref.current;
    if (e.pointerType === "touch" || !el || window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    const r = el.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width;
    const py = (e.clientY - r.top) / r.height;
    el.style.setProperty("--mx", `${px * 100}%`);
    el.style.setProperty("--my", `${py * 100}%`);
    el.style.transform = `perspective(900px) rotateX(${(0.5 - py) * max}deg) rotateY(${(px - 0.5) * max}deg) translateY(-4px)`;
  }
  function reset() {
    const el = ref.current;
    if (el) { el.style.transform = ""; el.style.removeProperty("--mx"); el.style.removeProperty("--my"); }
  }

  const Tag = as as "div";
  return (
    <Tag
      ref={ref as React.Ref<HTMLDivElement>}
      className={`pq-card pq-tilt ${className}`}
      style={style}
      onPointerMove={onMove}
      onPointerLeave={reset}
      onPointerCancel={reset}
    >
      {children}
    </Tag>
  );
}
