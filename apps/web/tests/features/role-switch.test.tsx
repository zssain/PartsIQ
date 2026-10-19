// F03 role switch — a presentational, accessible Customer ⇄ Reviewer toggle over one session.
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { RoleSwitch } from "@/components/live/RoleSwitch";

describe("RoleSwitch (F03)", () => {
  it("renders an accessible tablist with both roles and marks the active one selected", () => {
    render(<RoleSwitch role="customer" onChange={() => {}} />);
    const tablist = screen.getByRole("tablist", { name: /demo role/i });
    expect(tablist).toBeInTheDocument();
    expect(screen.getByTestId("role-customer")).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("role-reviewer")).toHaveAttribute("aria-selected", "false");
  });

  it("emits the other role when the inactive tab is clicked", async () => {
    const onChange = vi.fn();
    render(<RoleSwitch role="customer" onChange={onChange} />);
    await userEvent.click(screen.getByTestId("role-reviewer"));
    expect(onChange).toHaveBeenCalledWith("reviewer");
  });

  it("reflects the reviewer role as selected when passed in", () => {
    render(<RoleSwitch role="reviewer" onChange={() => {}} />);
    expect(screen.getByTestId("role-reviewer")).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("role-customer")).toHaveAttribute("aria-selected", "false");
  });
});
