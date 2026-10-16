// F37 Review workspace — assemble panels, show verification failures, empty states, stale guard.
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const apiMock = vi.fn();
vi.mock("@/lib/api", () => ({
  api: (...args: unknown[]) => apiMock(...args),
  ApiError: class ApiError extends Error {
    status = 0;
  },
}));

import { Workspace } from "@/components/review/Workspace";
import type { CandidateView, ReviewView } from "@/lib/contracts";

function enquiry(status: ReviewView["enquiry"]["status"], revision = 1): ReviewView["enquiry"] {
  return {
    id: "e1", revision, status, item_ids: [], catalogue_version_id: null, updated_at: "2026-10-17T12:00:00Z",
    messages: [{ id: "m1", enquiry_id: "e1", revision, kind: "customer", body: "need a fuel filter", created_at: "2026-10-17T11:00:00Z" }],
  };
}

function candidate(): CandidateView {
  return {
    item_id: "i1", revision: 1, part_id: 10, part_number: "VP-FF-10", name_en: "fuel filter", name_ar: "فلتر وقود",
    score: 0.91, reasons: ["lexical_match"], source_reference: "SYNTH-CA-PB-CA-110 rev 1, section FILTERS",
    evidence_id: "ev1", stock: [{ part_id: 10, warehouse_id: 1, available: "5", updated_at: "2026-10-17T10:00:00Z" }],
  };
}

describe("Workspace (F37)", () => {
  beforeEach(() => apiMock.mockReset());

  it("assembles panels and shows verification failures; approve disabled when not verified", async () => {
    const review: ReviewView = {
      enquiry: enquiry("awaiting_review"),
      facts: {}, draft: { greeting: "Hello", explanation: "Reviewed", closing: "Thanks" },
      verification: { passed: false, failures: [{ code: "OVERALLOCATION", item_id: null, detail: "exceeds stock" }], facts_sha256: "a".repeat(64) },
      assigned_to: null,
    };
    apiMock.mockResolvedValue({ review, candidates: [candidate()], notes: ["staff only note"] });
    render(<Workspace enquiryId="e1" />);

    expect(await screen.findByTestId("verification-failures")).toHaveTextContent("OVERALLOCATION");
    expect(screen.getByText(/staff only note/i)).toBeInTheDocument();     // notes panel
    expect(screen.getByText(/need a fuel filter/i)).toBeInTheDocument();  // customer messages panel (separate)
    expect(screen.getByTestId("approve")).toBeDisabled();                 // failed verification blocks approve
  });

  it("shows explicit empty states for missing panels", async () => {
    const review: ReviewView = {
      enquiry: enquiry("processing"), facts: null, draft: null, verification: null, assigned_to: null,
    };
    apiMock.mockResolvedValue({ review, candidates: [], notes: [] });
    render(<Workspace enquiryId="e1" />);

    expect(await screen.findByTestId("candidates-empty")).toBeInTheDocument();
    expect(screen.getByTestId("verification-empty")).toBeInTheDocument();
    expect(screen.getByTestId("draft-empty")).toBeInTheDocument();
    expect(screen.getByTestId("notes-empty")).toBeInTheDocument();
  });
});
