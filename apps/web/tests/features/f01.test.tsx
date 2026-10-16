// F01 Branded landing — journey, synthetic-demo notice, demo/architecture links, logo.
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const startAnonymousDemo = vi.fn();
vi.mock("@/lib/auth", () => ({ startAnonymousDemo: () => startAnonymousDemo() }));

import LandingPage from "@/app/page";

describe("LandingPage (F01)", () => {
  beforeEach(() => {
    push.mockReset();
    startAnonymousDemo.mockReset();
    delete process.env.NEXT_PUBLIC_REPO_URL;
  });

  it("explains the journey and shows the synthetic-demo notice without an affiliation claim", () => {
    render(<LandingPage />);
    expect(screen.getByTestId("synthetic-notice").textContent).toMatch(/synthetic/i);
    expect(screen.getByTestId("synthetic-notice").textContent).toMatch(/not affiliated/i);
    expect(screen.getByText(/identifies the machine/i)).toBeInTheDocument();
    expect(screen.getByText(/human reviewer must approve/i)).toBeInTheDocument();
  });

  it("shows the logo with meaningful alt text", () => {
    render(<LandingPage />);
    const logo = screen.getByAltText(/partsiq/i);
    expect(logo).toBeInTheDocument();
    expect(logo.getAttribute("alt")!.length).toBeGreaterThan(5);
  });

  it("starts the demo and navigates on click", async () => {
    startAnonymousDemo.mockResolvedValue({ id: "s1", generation: 1, expires_at: "2026-10-18T00:00:00Z" });
    render(<LandingPage />);
    await userEvent.click(screen.getByRole("button", { name: /start demo/i }));
    expect(startAnonymousDemo).toHaveBeenCalledOnce();
    expect(push).toHaveBeenCalledWith("/demo");
  });

  it("exposes the architecture link and hides the repo link when unconfigured", () => {
    render(<LandingPage />);
    expect(screen.getByText(/architecture/i)).toBeInTheDocument();
    expect(screen.queryByText(/source code/i)).toBeNull();
  });
});
