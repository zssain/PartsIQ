"use client";

import { Sun, Moon } from "lucide-react";
import { useEffect, useState, type JSX } from "react";

import {
  applyTheme,
  persistTheme,
  readSavedTheme,
  resolve_theme,
  systemPrefersDark,
  type Theme,
} from "@/lib/features/f08_light_and_dark_themes";

// Compact header theme control (reuses the F08 pure lib). Client-only init so SSR is deterministic
// (no hydration mismatch); applies the theme via the DOM attribute and persists it.
export function ThemeControl(): JSX.Element {
  const [theme, setTheme] = useState<Theme>("dark");

  useEffect(() => {
    const t = resolve_theme({ saved: readSavedTheme(), prefersDark: systemPrefersDark() }).theme;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- saved theme and prefers-color-scheme exist only in the browser; read once after hydration so SSR stays deterministic
    setTheme(t);
    applyTheme(t);
  }, []);

  function toggle() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    applyTheme(next);
    persistTheme(next);
  }

  return (
    <button
      type="button"
      className="pq-btn pq-btn-ghost"
      aria-pressed={theme === "dark"}
      aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
      onClick={toggle}
      style={{ padding: "0.5rem 0.7rem" }}
    >
      <span aria-hidden="true">{theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}</span>
    </button>
  );
}
