// LIVE review workspace (F03 reviewer). Covers: the three distinct regions, approve calls the
// endpoint exactly once then re-fetches the authoritative resource (never optimistic), reject
// requires a reason, a 409 preserves input and shows "data changed — reload", and a foreign id
// (404) renders the honest "not available" state.
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const getWorkspace = vi.fn();
const approveReview = vi.fn();
const rejectReview = vi.fn();

vi.mock("@/lib/api", () => ({
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
vi.mock("@/lib/live", () => ({
  getWorkspace: (...a: unknown[]) => getWorkspace(...a),
  approveReview: (...a: unknown[]) => approveReview(...a),
  rejectReview: (...a: unknown[]) => rejectReview(...a),
}));

import { ReviewWorkspaceLive } from "@/components/live/ReviewWorkspaceLive";
import { ApiError } from "@/lib/api";
import type { ReviewView } from "@/lib/live";

function workspace(status: ReviewView["enquiry"]["status"] = "awaiting_review", revision = 3): ReviewView {
  return {
    enquiry: { id: "e1", revision, status, messages: [], item_ids: [], catalogue_version_id: null, updated_at: "t" },
    facts: {
      items: [
        {
          part_number: "CA-AF-8973",
          name_en: "air filter",
          name_ar: "فلتر",
          requested_quantity: 2,
          allocations: [{ warehouse_id: 1, quantity: 2, transfer_days: 0 }],
          source_reference: "SYNTH-CA rev 1, section FILTERS",
        },
      ],
    },
    draft: { greeting: "Hello", explanation: "We suggest CA-AF-8973.", closing: "Thanks" },
    verification: { passed: true, failures: [], facts_sha256: "a".repeat(64) },
    assigned_to: null,
  };
}

describe("ReviewWorkspaceLive (F03 reviewer)", () => {
  beforeEach(() => {
    getWorkspace.mockReset();
    approveReview.mockReset();
    rejectReview.mockReset();
  });

  it("keeps AI suggestion, Database evidence and Human decision regions distinct", async () => {
    getWorkspace.mockResolvedValue(workspace());
    render(<ReviewWorkspaceLive enquiryId="e1" onBack={() => {}} />);

    const ai = await screen.findByTestId("region-ai-suggestion");
    const evidence = screen.getByTestId("region-database-evidence");
    const human = screen.getByTestId("region-human-decision");

    expect(within(ai).getByTestId("ai-draft")).toHaveTextContent("We suggest CA-AF-8973.");
    expect(within(evidence).getByTestId("evidence-source")).toHaveTextContent("SYNTH-CA rev 1");
    expect(within(evidence).getByTestId("evidence-allocation")).toHaveTextContent(/Warehouse 1/);
    // the draft prose is NOT duplicated into the evidence region.
    expect(within(evidence).queryByText(/We suggest CA-AF-8973\./)).toBeNull();
    // decision controls live only in the human region.
    expect(within(human).getByTestId("approve")).toBeInTheDocument();
    expect(within(ai).queryByTestId("approve")).toBeNull();
  });

  it("approve calls the endpoint once with the current revision, then re-fetches authoritative state", async () => {
    getWorkspace.mockResolvedValueOnce(workspace("awaiting_review", 3)); // initial load
    approveReview.mockResolvedValueOnce({ decision_id: "d1", message_id: "m1", revision: 4, already_applied: false });
    getWorkspace.mockResolvedValueOnce(workspace("approved", 4)); // authoritative re-fetch
    render(<ReviewWorkspaceLive enquiryId="e1" onBack={() => {}} />);

    await userEvent.click(await screen.findByTestId("approve"));

    expect(approveReview).toHaveBeenCalledTimes(1);
    expect(approveReview).toHaveBeenCalledWith("e1", 3); // uses the workspace's current revision
    // approval is shown only AFTER the authoritative re-fetch (not optimistically).
    expect(getWorkspace).toHaveBeenCalledTimes(2);
    expect(await screen.findByTestId("decision-outcome")).toHaveTextContent(/approved/);
  });

  it("reject requires a reason before calling the endpoint", async () => {
    getWorkspace.mockResolvedValue(workspace());
    render(<ReviewWorkspaceLive enquiryId="e1" onBack={() => {}} />);

    await userEvent.click(await screen.findByTestId("reject"));
    expect(rejectReview).not.toHaveBeenCalled();
    expect(screen.getByTestId("decision-error")).toHaveTextContent(/reason is required/i);

    rejectReview.mockResolvedValueOnce({ decision_id: "d2", revision: 4, status: "rejected" });
    getWorkspace.mockResolvedValueOnce(workspace("rejected", 4));
    await userEvent.type(screen.getByTestId("reject-reason"), "part does not fit");
    await userEvent.click(screen.getByTestId("reject"));
    expect(rejectReview).toHaveBeenCalledWith("e1", 3, "part does not fit");
  });

  it("on a 409 preserves the typed reason and shows 'data changed — reload'", async () => {
    getWorkspace.mockResolvedValue(workspace());
    approveReview.mockRejectedValueOnce(new ApiError("CONFLICT", 409, "stale", "req-409"));
    render(<ReviewWorkspaceLive enquiryId="e1" onBack={() => {}} />);

    await screen.findByTestId("approve");
    await userEvent.type(screen.getByTestId("reject-reason"), "my reason");
    await userEvent.click(screen.getByTestId("approve"));

    expect(await screen.findByTestId("decision-error")).toHaveTextContent(/data changed/i);
    expect(screen.getByTestId("decision-error")).toHaveTextContent("req-409");
    // input is preserved (not cleared) and a reload control appears.
    expect(screen.getByTestId("reject-reason")).toHaveValue("my reason");
    expect(screen.getByTestId("workspace-reload")).toBeInTheDocument();
  });

  it("renders an honest 'not available' state for a foreign enquiry (404)", async () => {
    getWorkspace.mockRejectedValueOnce(new ApiError("NOT_FOUND", 404, "nope", "req-404"));
    render(<ReviewWorkspaceLive enquiryId="foreign" onBack={() => {}} />);
    expect(await screen.findByTestId("workspace-not-available")).toHaveTextContent(/not available/i);
    expect(screen.getByTestId("workspace-not-available")).toHaveTextContent("req-404");
  });
});
