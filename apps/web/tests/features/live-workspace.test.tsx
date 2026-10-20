// Command workspace (/demo/live) shell behaviour: query-string navigation with browser history,
// same-tab restore of the active enquiry, a non-destructive "New enquiry", honest labelling of the
// unconnected collaboration capability, and the EN/AR control that the hidden site header used to
// provide. Child panels are stubbed — their own suites cover the API-connected flows.
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }));
vi.mock("@/lib/live", () => ({ ensureDemoToken: vi.fn(() => "demo-token") }));
vi.mock("@/components/live/CustomerLive", () => ({
  CustomerLive: ({ enquiryId, onCreated }: { enquiryId: string | null; onCreated: (id: string) => void }) => (
    <div data-testid="customer-live" data-enquiry={enquiryId ?? ""}>
      <button type="button" onClick={() => onCreated("enq-new")}>stub-create</button>
    </div>
  ),
}));
vi.mock("@/components/live/ReviewerInbox", () => ({ ReviewerInbox: () => <div data-testid="reviewer-inbox-stub" /> }));
vi.mock("@/components/live/ReviewWorkspaceLive", () => ({ ReviewWorkspaceLive: () => <div /> }));
vi.mock("@/components/visibility/SpecialistTimeline", () => ({
  SpecialistTimeline: ({ enquiryId }: { enquiryId: string }) => <div data-testid="timeline" data-enquiry={enquiryId} />,
}));

import { LiveDemo } from "@/components/live/LiveDemo";

describe("LiveDemo command workspace", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;
  beforeEach(() => {
    sessionStorage.clear();
    window.history.replaceState(null, "", "/demo/live");
    fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
  });
  afterEach(() => vi.unstubAllGlobals());

  it("restores the active enquiry from same-tab session storage on refresh", async () => {
    sessionStorage.setItem("pq-active-enquiry", "enq-123");
    render(<LiveDemo />);
    expect(await screen.findByTestId("customer-live")).toHaveAttribute("data-enquiry", "enq-123");
  });

  it("remembers a newly created enquiry for this tab", async () => {
    render(<LiveDemo />);
    await userEvent.click(await screen.findByText("stub-create"));
    expect(sessionStorage.getItem("pq-active-enquiry")).toBe("enq-new");
  });

  it("navigates screens through the query string and honours browser Back", async () => {
    sessionStorage.setItem("pq-active-enquiry", "enq-123");
    render(<LiveDemo />);
    await userEvent.click(await screen.findByRole("button", { name: /specialist activity/i }));
    expect(window.location.search).toBe("?view=activity");
    expect(screen.getByTestId("timeline")).toHaveAttribute("data-enquiry", "enq-123");

    // Simulate Back to the enquiries screen.
    act(() => {
      window.history.replaceState(null, "", "/demo/live?view=enquiry");
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    expect(screen.getByTestId("customer-live")).toBeInTheDocument();
  });

  it("does not push a duplicate history entry when re-selecting the current screen", async () => {
    render(<LiveDemo />);
    const before = window.history.length;
    await userEvent.click(await screen.findByRole("button", { name: /^enquiries$/i }));
    await userEvent.click(screen.getByRole("button", { name: /^enquiries$/i }));
    expect(window.history.length).toBe(before + 1);
  });

  it("New enquiry clears only the local pointer — no server call deletes records", async () => {
    sessionStorage.setItem("pq-active-enquiry", "enq-123");
    render(<LiveDemo />);
    await userEvent.click(await screen.findByRole("button", { name: /new enquiry/i }));
    expect(sessionStorage.getItem("pq-active-enquiry")).toBeNull();
    expect(screen.getByTestId("customer-live")).toHaveAttribute("data-enquiry", "");
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("labels agent collaboration as not connected and offers no pause/resume/cancel controls", async () => {
    window.history.replaceState(null, "", "/demo/live?view=overview");
    render(<LiveDemo />);
    expect(await screen.findByText(/agent collaboration/i)).toBeInTheDocument();
    expect(screen.getByText(/not connected/i)).toBeInTheDocument();
    for (const name of [/pause/i, /resume/i, /cancel/i]) {
      expect(screen.queryByRole("button", { name })).toBeNull();
    }
  });

  it("keeps the EN/AR locale control, the brand logo and the synthetic-data label on this route", async () => {
    render(<LiveDemo />);
    expect(await screen.findByRole("group", { name: /language/i })).toBeInTheDocument();
    expect(screen.getByAltText(/partsiq/i)).toBeInTheDocument();
    expect(screen.getAllByText(/synthetic/i).length).toBeGreaterThan(0);
    expect(screen.getByText("Synthetic demo")).toBeInTheDocument();
  });
});
