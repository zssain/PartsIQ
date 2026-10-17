import { type JSX } from "react";

// Oil-slick aurora backdrop: two slowly counter-rotating conic-gradient blobs, blurred, fixed
// behind all content. Pure CSS (keyframes in tokens.css); honors prefers-reduced-motion.
export function Aurora(): JSX.Element {
  return <div className="pq-aurora" aria-hidden="true" />;
}
