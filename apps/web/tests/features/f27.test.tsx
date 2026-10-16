// F27 Match explanations — evidence-derived, HTML escaped, scores not labelled a probability.
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

const review: ReviewView = {
  enquiry: {
    id: "e1", revision: 1, status: "awaiting_review", messages: [], item_ids: [],
    catalogue_version_id: null, updated_at: "2026-10-17T12:00:00Z",
  },
  facts: {}, draft: null, verification: null, assigned_to: null,
};

function candidate(overrides: Partial<CandidateView> = {}): CandidateView {
  return {
    item_id: "i1", revision: 1, part_id: 10, part_number: "VP-FF-10", name_en: "fuel filter", name_ar: "فلتر وقود",
    score: 0.91, reasons: ["superseded_number_resolved", "lexical_match"],
    source_reference: "SYNTH-CA-PB-CA-110 rev 1, section FILTERS", evidence_id: "ev1",
    stock: [{ part_id: 10, warehouse_id: 1, available: "5", updated_at: "2026-10-17T10:00:00Z" }],
    ...overrides,
  };
}

describe("Match explanations (F27)", () => {
  beforeEach(() => apiMock.mockReset());

  it("shows evidence-derived reasons and a fitment reference, labelled a match score", async () => {
    apiMock.mockResolvedValue({ review, candidates: [candidate()], notes: [] });
    render(<Workspace enquiryId="e1" />);
    expect(await screen.findByTestId("explanation")).toHaveTextContent("superseded_number_resolved");
    expect(screen.getByTestId("evidence")).toHaveTextContent("SYNTH-CA-PB-CA-110 rev 1, section FILTERS");
    expect(screen.getByTestId("match-score").textContent).toMatch(/match score/i);
    expect(screen.getByTestId("match-score").textContent).not.toMatch(/probability/i);
  });

  it("shows absent evidence as unavailable", async () => {
    apiMock.mockResolvedValue({ review, candidates: [candidate({ source_reference: "" })], notes: [] });
    render(<Workspace enquiryId="e1" />);
    expect(await screen.findByTestId("evidence")).toHaveTextContent(/unavailable/i);
  });

  it("escapes user/catalogue HTML in names", async () => {
    apiMock.mockResolvedValue({ review, candidates: [candidate({ name_en: "<img src=x onerror=alert(1)>" })], notes: [] });
    const { container } = render(<Workspace enquiryId="e1" />);
    await screen.findByTestId("explanation");
    expect(container.querySelector("img[onerror]")).toBeNull(); // not parsed as markup
    expect(screen.getByText("<img src=x onerror=alert(1)>")).toBeInTheDocument(); // shown as text
  });
});
