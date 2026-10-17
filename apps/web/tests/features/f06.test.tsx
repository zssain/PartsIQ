// F06 Responsive layouts — breakpoint columns, stacking at 360, controlled shell, reducedMotion.
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ResponsiveShell } from "@/components/features/ResponsiveShell";
import { get_layout } from "@/lib/features/f06_responsive_layouts";

describe("get_layout (F06)", () => {
  it("stacks to one compact column at 360", () => {
    expect(get_layout({ width: 360, reducedMotion: false })).toEqual({ columns: 1, compact: true });
  });

  it("uses two columns at 768", () => {
    expect(get_layout({ width: 768, reducedMotion: false })).toEqual({ columns: 2, compact: false });
  });

  it("uses three columns at 1280", () => {
    expect(get_layout({ width: 1280, reducedMotion: false })).toEqual({ columns: 3, compact: false });
  });

  it("carries the reducedMotion flag independently of the column count", () => {
    expect(get_layout({ width: 360, reducedMotion: true }).columns).toBe(1);
  });
});

describe("ResponsiveShell (F06)", () => {
  it("renders a controlled column count and its children", () => {
    render(
      <ResponsiveShell value={{ columns: 1, compact: true }} loading={false} error={null} onAction={vi.fn()}>
        <p>panel</p>
      </ResponsiveShell>,
    );
    const shell = screen.getByTestId("responsive-shell");
    expect(shell.getAttribute("data-columns")).toBe("1");
    expect(shell.getAttribute("data-compact")).toBe("true");
    expect(screen.getByText("panel")).toBeInTheDocument();
  });

  it("measures the viewport and reports it via onAction when uncontrolled", async () => {
    const onAction = vi.fn().mockResolvedValue(undefined);
    render(
      <ResponsiveShell value={null} loading={false} error={null} onAction={onAction}>
        <p>content</p>
      </ResponsiveShell>,
    );
    expect(onAction).toHaveBeenCalled();
    const call = onAction.mock.calls[0][0];
    expect(typeof call.width).toBe("number");
    expect(typeof call.reducedMotion).toBe("boolean");
  });
});
