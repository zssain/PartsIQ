// F08 Light and dark themes — resolution precedence, accessible toggle, storage-disabled safety.
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ThemeToggle } from "@/components/features/ThemeToggle";
import { resolve_theme } from "@/lib/features/f08_light_and_dark_themes";

// A clean in-memory localStorage on window (jsdom's is unreliable across files here).
function installStorage(impl: Partial<Storage>) {
  const store: Record<string, string> = {};
  const base: Storage = {
    getItem: (k) => store[k] ?? null,
    setItem: (k, v) => {
      store[k] = v;
    },
    removeItem: (k) => {
      delete store[k];
    },
    clear: () => {
      for (const k of Object.keys(store)) delete store[k];
    },
    key: () => null,
    length: 0,
  };
  Object.defineProperty(window, "localStorage", { value: { ...base, ...impl }, configurable: true });
}

beforeEach(() => installStorage({}));
afterEach(() => vi.restoreAllMocks());

describe("resolve_theme (F08)", () => {
  it("prefers a saved value over the system setting", () => {
    expect(resolve_theme({ saved: "dark", prefersDark: false })).toEqual({ theme: "dark" });
    expect(resolve_theme({ saved: "light", prefersDark: true })).toEqual({ theme: "light" });
  });

  it("falls back to the system setting, defaulting to light", () => {
    expect(resolve_theme({ saved: null, prefersDark: true })).toEqual({ theme: "dark" });
    expect(resolve_theme({ saved: null, prefersDark: false })).toEqual({ theme: "light" });
  });
});

describe("ThemeToggle (F08)", () => {
  it("is an accessible toggle that flips and persists the theme", async () => {
    render(<ThemeToggle value={null} loading={false} error={null} onAction={vi.fn().mockResolvedValue(undefined)} />);
    const button = screen.getByRole("button");
    expect(button).toHaveAttribute("aria-pressed");
    await userEvent.click(button);
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(window.localStorage.getItem("pq-theme")).toBe("dark");
    expect(screen.getByTestId("active-theme")).toHaveTextContent("dark");
  });

  it("still works when storage is disabled", async () => {
    installStorage({
      setItem: () => {
        throw new Error("storage disabled");
      },
    });
    render(<ThemeToggle value={null} loading={false} error={null} onAction={vi.fn().mockResolvedValue(undefined)} />);
    await userEvent.click(screen.getByRole("button")); // must not throw
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark"); // applied via DOM attr
  });
});
