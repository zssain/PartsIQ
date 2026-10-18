// SpecialistTimeline visibility panel — staff view of the persisted timeline.
// Covers: loading→data (label/status/timestamp/evidence line, retries), empty, error+retry,
// and permission (403) states. No hidden chain-of-thought — only step outcomes.
import { render, screen } from "@testing-library/react";
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

import { SpecialistTimeline } from "@/components/visibility/SpecialistTimeline";
import { ApiError } from "@/lib/api";
import type { TimelineView } from "@/lib/live";

function timeline(): TimelineView {
  return {
    enquiry_id: "e1",
    events: [
      { step: "finding_parts", label: "Finding parts", at: "2026-10-19T10:02:00Z", status: "failed", detail: "catalogue lookup timed out", attempt: 1 },
      { step: "finding_parts_retry", label: "Finding parts", at: "2026-10-19T10:03:00Z", status: "done", detail: "matched 2 candidates", attempt: 2 },
    ],
  };
}

describe("SpecialistTimeline", () => {
  beforeEach(() => apiMock.mockReset());

  it("goes loading → data and shows label, status, timestamp, evidence line and retries", async () => {
    apiMock.mockResolvedValue(timeline());
    render(<SpecialistTimeline enquiryId="e1" />);

    expect(screen.getByTestId("timeline-loading")).toBeInTheDocument();

    expect(await screen.findByTestId("timeline-events")).toBeInTheDocument();
    expect(screen.getByTestId("status-finding_parts")).toHaveTextContent(/failed/i);
    expect(screen.getByTestId("evidence-finding_parts")).toHaveTextContent(/catalogue lookup timed out/i);
    expect(screen.getByTestId("attempt-finding_parts_retry")).toHaveTextContent(/attempt 2/i);
    // timestamp rendered via <time dateTime>
    const times = document.querySelectorAll("time");
    expect(times[0].getAttribute("dateTime")).toBe("2026-10-19T10:02:00Z");
  });

  it("shows an explicit empty state with no events", async () => {
    apiMock.mockResolvedValue({ enquiry_id: "e1", events: [] } satisfies TimelineView);
    render(<SpecialistTimeline enquiryId="e1" />);
    expect(await screen.findByTestId("timeline-empty")).toBeInTheDocument();
  });

  it("shows an error with request id and retries", async () => {
    apiMock.mockRejectedValueOnce(new ApiError("DEPENDENCY_UNAVAILABLE", 500, "boom", "req-9"));
    render(<SpecialistTimeline enquiryId="e1" />);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("boom");
    expect(alert).toHaveTextContent("req-9");

    apiMock.mockResolvedValueOnce(timeline());
    await userEvent.click(screen.getByTestId("timeline-retry"));
    expect(await screen.findByTestId("timeline-events")).toBeInTheDocument();
  });

  it("shows an honest permission state on 403 with the request id", async () => {
    apiMock.mockRejectedValueOnce(new ApiError("FORBIDDEN", 403, "nope", "req-403"));
    render(<SpecialistTimeline enquiryId="e1" />);
    expect(await screen.findByTestId("timeline-permission")).toHaveTextContent("req-403");
  });
});
