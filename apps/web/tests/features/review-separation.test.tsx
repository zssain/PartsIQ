// ReviewSeparation visibility panel — three distinct regions + approve control.
// Covers: loading→data, the three labelled regions stay distinct, the approve control calls the
// endpoint exactly once, empty, error+retry, and permission (403) states.
import { render, screen, within } from "@testing-library/react";
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

import { ReviewSeparation } from "@/components/visibility/ReviewSeparation";
import { ApiError } from "@/lib/api";
import type { CandidateView, ReviewView } from "@/lib/contracts";

function reviewPayload(status: ReviewView["enquiry"]["status"] = "awaiting_review") {
  const enquiry: ReviewView["enquiry"] = {
    id: "e1", revision: 1, status, item_ids: [], catalogue_version_id: null, updated_at: "2026-10-19T12:00:00Z",
    messages: [],
  };
  const review: ReviewView = {
    enquiry,
    facts: {},
    draft: { greeting: "Hello", explanation: "We suggest part VP-FF-10.", closing: "Thanks" },
    verification: { passed: true, failures: [], facts_sha256: "a".repeat(64) },
    assigned_to: null,
  };
  const candidates: CandidateView[] = [{
    item_id: "i1", revision: 1, part_id: 10, part_number: "VP-FF-10", name_en: "fuel filter", name_ar: "فلتر",
    score: 0.91, reasons: ["lexical_match"], source_reference: "SYNTH-CA rev 1, section FILTERS",
    evidence_id: "ev1", stock: [{ part_id: 10, warehouse_id: 1, available: "5", updated_at: "2026-10-19T10:00:00Z" }],
  }];
  return { review, candidates };
}

describe("ReviewSeparation", () => {
  beforeEach(() => apiMock.mockReset());

  it("keeps AI suggestion, Database evidence and Human decision regions distinct", async () => {
    apiMock.mockResolvedValue(reviewPayload());
    render(<ReviewSeparation enquiryId="e1" />);

    const ai = await screen.findByTestId("region-ai-suggestion");
    const evidence = screen.getByTestId("region-database-evidence");
    const human = screen.getByTestId("region-human-decision");

    // AI suggestion holds the model's draft; database evidence holds the source + stock.
    expect(within(ai).getByTestId("ai-draft")).toHaveTextContent("We suggest part VP-FF-10.");
    expect(within(evidence).getByTestId("evidence-source")).toHaveTextContent("SYNTH-CA rev 1");
    expect(within(evidence).getByTestId("evidence-stock")).toHaveTextContent(/5 available/);
    // the draft prose is NOT duplicated into the evidence region (regions are distinct).
    expect(within(evidence).queryByText(/We suggest part VP-FF-10\./)).toBeNull();
    // the decision control lives only in the human region.
    expect(within(human).getByTestId("approve")).toBeInTheDocument();
    expect(within(ai).queryByTestId("approve")).toBeNull();
  });

  it("the approve control calls the approve endpoint exactly once", async () => {
    apiMock.mockResolvedValueOnce(reviewPayload()); // workspace load
    apiMock.mockResolvedValueOnce({ id: "e1", revision: 2, status: "approved", messages: [], item_ids: [], catalogue_version_id: null, updated_at: "t" }); // approve
    render(<ReviewSeparation enquiryId="e1" />);

    const approve = await screen.findByTestId("approve");
    await userEvent.click(approve);

    const approveCalls = apiMock.mock.calls.filter((c) => String(c[0]).endsWith("/approve"));
    expect(approveCalls).toHaveLength(1);
    expect(approveCalls[0][1]).toMatchObject({ method: "POST" });
    // the approve call carries an idempotency key
    const headers = (approveCalls[0][1] as { headers: Record<string, string> }).headers;
    expect(headers["idempotency-key"]).toBeTruthy();
    expect(await screen.findByTestId("decision-outcome")).toHaveTextContent(/approved/);
  });

  it("shows an explicit empty AI state when there is no draft or candidate", async () => {
    const payload = reviewPayload();
    payload.review.draft = null;
    payload.candidates = [];
    apiMock.mockResolvedValue(payload);
    render(<ReviewSeparation enquiryId="e1" />);
    expect(await screen.findByTestId("ai-draft-empty")).toBeInTheDocument();
    expect(screen.getByTestId("evidence-empty")).toBeInTheDocument();
  });

  it("shows an error with request id and retries the load", async () => {
    apiMock.mockRejectedValueOnce(new ApiError("DEPENDENCY_UNAVAILABLE", 500, "down", "req-5"));
    render(<ReviewSeparation enquiryId="e1" />);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("down");
    expect(alert).toHaveTextContent("req-5");

    apiMock.mockResolvedValueOnce(reviewPayload());
    await userEvent.click(screen.getByTestId("review-retry"));
    expect(await screen.findByTestId("region-ai-suggestion")).toBeInTheDocument();
  });

  it("shows an honest permission state on 403 with the request id", async () => {
    apiMock.mockRejectedValueOnce(new ApiError("FORBIDDEN", 403, "nope", "req-403"));
    render(<ReviewSeparation enquiryId="e1" />);
    expect(await screen.findByTestId("review-permission")).toHaveTextContent("req-403");
  });
});
