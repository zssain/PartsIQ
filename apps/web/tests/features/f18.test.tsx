// F18 Progress timeline — persisted stages, customer-vs-staff wait, no fabricated completion.
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Timeline } from "@/components/review/Timeline";
import type { EnquiryView } from "@/lib/contracts";

function enquiry(status: EnquiryView["status"]): EnquiryView {
  return {
    id: "e1", revision: 1, status, messages: [], item_ids: [],
    catalogue_version_id: null, updated_at: "2026-10-17T12:00:00Z",
  };
}

describe("Timeline (F18)", () => {
  it("shows the real stage reached and does not fabricate completion", () => {
    render(<Timeline enquiry={enquiry("awaiting_review")} lastUpdated="2026-10-17T12:00:00Z" pollFailed={false} onRetry={vi.fn()} />);
    const stages = screen.getAllByRole("listitem");
    const approved = stages.find((li) => li.textContent === "approved")!;
    const awaiting = stages.find((li) => li.textContent === "awaiting_review")!;
    expect(awaiting.getAttribute("data-reached")).toBe("true");
    expect(approved.getAttribute("data-reached")).toBe("false"); // not approved yet
  });

  it("separates waiting-for-customer from waiting-for-staff", () => {
    const { rerender } = render(<Timeline enquiry={enquiry("needs_information")} lastUpdated={null} pollFailed={false} onRetry={vi.fn()} />);
    expect(screen.getByTestId("wait-reason").textContent).toMatch(/customer/i);
    rerender(<Timeline enquiry={enquiry("awaiting_review")} lastUpdated={null} pollFailed={false} onRetry={vi.fn()} />);
    expect(screen.getByTestId("wait-reason").textContent).toMatch(/staff/i);
  });

  it("retains state and offers retry on a failed poll", async () => {
    const onRetry = vi.fn();
    render(<Timeline enquiry={enquiry("processing")} lastUpdated="2026-10-17T12:00:00Z" pollFailed={true} onRetry={onRetry} />);
    expect(screen.getByTestId("timeline")).toBeInTheDocument(); // last state retained
    await userEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("shows an empty state before any status", () => {
    render(<Timeline enquiry={null} lastUpdated={null} pollFailed={false} onRetry={vi.fn()} />);
    expect(screen.getByTestId("timeline-empty")).toBeInTheDocument();
  });
});
