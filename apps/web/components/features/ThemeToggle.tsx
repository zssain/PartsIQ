"use client";

import { useEffect, useState, type JSX } from "react";

import type { ApiError } from "@/lib/api";
import {
  applyTheme,
  persistTheme,
  readSavedTheme,
  resolve_theme,
  systemPrefersDark,
  type F08Request,
  type F08Result,
  type Theme,
} from "@/lib/features/f08_light_and_dark_themes";

// F08 Theme toggle — an accessible button that flips light/dark. It initializes from the saved
// preference then the system setting, applies the theme via a DOM attribute (no React-managed
// attribute, so no hydration mismatch), and persists the choice (a storage-disabled browser
// still works for the session). Submits only the typed preference.
export function ThemeToggle(props: {
  value: F08Result | null;
  loading: boolean;
  error: ApiError | null;
  onAction: (request: F08Request) => Promise<void>;
}): JSX.Element {
  const { value, loading, error, onAction } = props;
  const [theme, setTheme] = useState<Theme>(value?.theme ?? "light");

  useEffect(() => {
    // Client-only initialization so SSR stays deterministic (no hydration mismatch).
    const initial = resolve_theme({ saved: readSavedTheme(), prefersDark: systemPrefersDark() }).theme;
    setTheme(initial);
    applyTheme(initial);
  }, []);

  async function toggle() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    applyTheme(next);
    persistTheme(next);
    await onAction({ saved: next, prefersDark: systemPrefersDark() });
  }

  const shown = value?.theme ?? theme;
  return (
    <section aria-label="Theme" data-testid="theme-toggle">
      <button type="button" aria-pressed={shown === "dark"} onClick={toggle} disabled={loading}>
        {shown === "dark" ? "Switch to light theme" : "Switch to dark theme"}
      </button>
      {error ? <p role="alert">{error.message}</p> : null}
      <span data-testid="active-theme">{shown}</span>
    </section>
  );
}
