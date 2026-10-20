"use client";

import { useEffect, useRef, useState, type CSSProperties, type JSX, type ReactNode } from "react";

// Scroll-reveal: fades + lifts children into view once, via IntersectionObserver. `delay` staggers
// siblings. Reduced-motion users see content immediately (tokens.css neutralizes the transform).
export function Reveal({
  children,
  className = "",
  delay = 0,
  as = "div",
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
  as?: "div" | "section" | "li" | "article";
}): JSX.Element {
  const ref = useRef<HTMLElement>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- no IntersectionObserver (jsdom/old browsers): show immediately; the server render must stay hidden to match
      setShown(true); // no observer (SSR/jsdom): show content immediately
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          setShown(true);
          io.disconnect();
        }
      },
      { threshold: 0.12 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  const Tag = as as "div";
  const style: CSSProperties = { transitionDelay: `${delay}ms` };
  return (
    <Tag ref={ref as React.Ref<HTMLDivElement>} className={`pq-reveal ${shown ? "pq-in" : ""} ${className}`} style={style}>
      {children}
    </Tag>
  );
}
