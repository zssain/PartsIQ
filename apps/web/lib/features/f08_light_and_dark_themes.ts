// F08 Light and dark themes (owner: web).
//
// Pure theme resolution: a saved preference wins, otherwise the system (prefers-color-scheme)
// decides, defaulting to light. Reads/writes degrade gracefully when storage is unavailable.
// Components reference CSS semantic tokens (styles/tokens.css), never hard-coded hexes.

export type Theme = "light" | "dark";

export interface F08Request {
  saved: Theme | null;
  prefersDark: boolean;
}

export interface F08Result {
  theme: Theme;
}

const STORAGE_KEY = "pq-theme";

export function resolve_theme(request: F08Request): F08Result {
  if (request.saved === "light" || request.saved === "dark") {
    return { theme: request.saved };
  }
  return { theme: request.prefersDark ? "dark" : "light" };
}

export function systemPrefersDark(): boolean {
  try {
    return typeof window !== "undefined" && !!window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  } catch {
    return false;
  }
}

export function readSavedTheme(): Theme | null {
  try {
    const value = typeof window !== "undefined" ? window.localStorage.getItem(STORAGE_KEY) : null;
    return value === "light" || value === "dark" ? value : null;
  } catch {
    return null; // storage disabled: fall back to the system preference
  }
}

export function persistTheme(theme: Theme): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // storage disabled: the theme still applies for this session via the DOM attribute
  }
}

export function applyTheme(theme: Theme): void {
  try {
    document.documentElement.setAttribute("data-theme", theme);
  } catch {
    // no document (SSR/tests without DOM): nothing to apply
  }
}
