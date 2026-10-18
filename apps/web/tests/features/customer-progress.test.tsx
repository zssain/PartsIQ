// CustomerProgress visibility panel — persisted-timeline-driven step list.
// Covers: loading→data (renders persisted events, highlights the current step), empty, error+retry,
// and permission (403) states; the current-step highlight follows ACTUAL event status.
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const apiMock = vi.fn();
vi.mock("@/lib/api", () => ({
  api: (...args: unknown[]) => apiMock(...args),
  ApiError: class ApiError extends Error {
    code: string;
    status: number;
    requestId: string | null;
    constructor(code: string, status: number, message: string, requestId: string | null) {
      super(message);
      this.code = code;
      this.status = status;
      this.requestId = requestId;
    }
  },
}));

import { CustomerProgress } from "@/components/visibility/CustomerProgress";
import { ApiError } from "@/lib/api";
import type { TimelineView } from "@/lib/live";

function timeline(): TimelineView {
  return {
    enquiry_id: "e1",
    events: [
      { step: "reading", label: "Reading request", at: "2026-10-19T10:00:00Z", status: "done" },
      { step: "identifying", label: "Identifying", at: "2026-10-19T10:01:00Z", status: "done" },
      { step: "finding_parts", label: "Finding parts", at: "2026-10-19T10:02:00Z", status: "running" },
    ],
  };
}

describe("CustomerProgress", () => {
  beforeEach(() => apiMock.mockReset());

  it("goes loading → data, renders persisted events and highlights the current step", async () => {
    apiMock.mockResolvedValue(timeline());
    render(<CustomerProgress enquiryId="e1" />);

    expect(screen.getByTestId("progress-loading")).toBeInTheDocument();

    const steps = await screen.findByTestId("progress-steps");
    expect(steps).toBeInTheDocument();
    // persisted "done" events are shown done, not fabricated upcoming.
    expect(screen.getByText("Reading request").closest("li")).toHaveAttribute("data-stage", "done");
    // current step = the furthest recorded step (finding_parts) is highlighted.
    const current = screen.getByText("Finding parts").closest("li");
    expect(current).toHaveAttribute("data-current", "true");
    expect(current).toHaveAttribute("aria-current", "step");
    // a step the server has NOT recorded stays upcoming (never a fake spinner ahead of real state).
    expect(screen.getByText("Planning").closest("li")).toHaveAttribute("data-stage", "upcoming");
  });

  it("shows the wait reason from a persisted waiting event", async () => {
    apiMock.mockResolvedValue({
      enquiry_id: "e1",
      events: [
        { step: "reading", label: "Reading request", at: "t", status: "done" },
        { step: "awaiting_review", label: "Waiting for review", at: "t", status: "waiting", detail: "Awaiting human review" },
      ],
    } satisfies TimelineView);
    render(<CustomerProgress enquiryId="e1" />);
    expect(await screen.findByTestId("wait-reason")).toHaveTextContent(/awaiting human review/i);
  });

  it("shows an explicit empty state when there are no events yet", async () => {
    apiMock.mockResolvedValue({ enquiry_id: "e1", events: [] } satisfies TimelineView);
    render(<CustomerProgress enquiryId="e1" />);
    expect(await screen.findByTestId("progress-empty")).toBeInTheDocument();
  });

  it("shows an error with the request id and a retry that reloads", async () => {
    apiMock.mockRejectedValueOnce(new ApiError("DEPENDENCY_UNAVAILABLE", 500, "upstream down", "req-123"));
    render(<CustomerProgress enquiryId="e1" />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("upstream down");
    expect(alert).toHaveTextContent("req-123");

    apiMock.mockResolvedValueOnce(timeline());
    await userEvent.click(screen.getByTestId("progress-retry"));
    expect(await screen.findByTestId("progress-steps")).toBeInTheDocument();
  });

  it("shows an honest permission state on 403 and surfaces the request id", async () => {
    // A permission error is terminal: the component stops polling, so exactly one call rejects.
    apiMock.mockRejectedValueOnce(new ApiError("FORBIDDEN", 403, "forbidden", "req-403"));
    render(<CustomerProgress enquiryId="e1" />);
    await waitFor(() => expect(screen.getByTestId("progress-permission")).toBeInTheDocument());
    expect(screen.getByTestId("progress-permission")).toHaveTextContent("req-403");
  });
});
