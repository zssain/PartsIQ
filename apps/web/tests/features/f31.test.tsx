// F31 Candidate comparison — compare 2-3 candidates from the same item/revision; select sends id only.
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CandidateComparison } from "@/components/features/CandidateComparison";
import { compare_candidates, type F31Request } from "@/lib/features/f31_candidate_comparison";
import type { CandidateView } from "@/lib/contracts";

function candidate(overrides: Partial<CandidateView> = {}): CandidateView {
  return {
    item_id: "i1", revision: 1, part_id: 10, part_number: "VP-FF-10", name_en: "fuel filter", name_ar: "فلتر وقود",
    score: 0.9, reasons: ["lexical_match"],
    source_reference: "SYNTH-CA-PB-CA-110 rev 1, section FILTERS", evidence_id: "ev1",
    stock: [{ part_id: 10, warehouse_id: 1, available: "5", updated_at: "2026-10-17T10:00:00Z" }],
    ...overrides,
  };
}

describe("compare_candidates (F31)", () => {
  it("compares two candidates from the same item/revision", () => {
    const candidates = [candidate(), candidate({ part_id: 11, part_number: "VP-FF-11", name_en: "filter v2" })];
    const result = compare_candidates({ candidates, selectedIds: [10, 11] });
    const partRow = result.rows.find((r) => r.attribute === "Part number")!;
    expect(partRow.values).toEqual(["VP-FF-10", "VP-FF-11"]);
    const avail = result.rows.find((r) => r.attribute === "Availability")!;
    expect(avail.values).toEqual(["5", "5"]);
  });

  it("supports three candidates", () => {
    const candidates = [candidate(), candidate({ part_id: 11 }), candidate({ part_id: 12 })];
    const result = compare_candidates({ candidates, selectedIds: [10, 11, 12] });
    expect(result.rows[0].values).toHaveLength(3);
  });

  it("shows a missing attribute as null (rendered unavailable)", () => {
    const candidates = [candidate(), candidate({ part_id: 11, source_reference: "", stock: [] })];
    const result = compare_candidates({ candidates, selectedIds: [10, 11] });
    const evidence = result.rows.find((r) => r.attribute === "Evidence")!;
    expect(evidence.values[1]).toBeNull();
    const avail = result.rows.find((r) => r.attribute === "Availability")!;
    expect(avail.values[1]).toBeNull();
  });

  it("rejects a foreign candidate id", () => {
    expect(() => compare_candidates({ candidates: [candidate()], selectedIds: [10, 999] })).toThrow(/foreign/i);
  });

  it("rejects candidates from a different revision (stale)", () => {
    const candidates = [candidate(), candidate({ part_id: 11, revision: 2 })];
    expect(() => compare_candidates({ candidates, selectedIds: [10, 11] })).toThrow(/same item and revision/i);
  });

  it("rejects fewer than two or more than three", () => {
    expect(() => compare_candidates({ candidates: [candidate()], selectedIds: [10] })).toThrow(/two or three/i);
    const four = [10, 11, 12, 13].map((id) => candidate({ part_id: id }));
    expect(() => compare_candidates({ candidates: four, selectedIds: [10, 11, 12, 13] })).toThrow(/two or three/i);
  });
});

describe("CandidateComparison component (F31)", () => {
  const candidates = [candidate(), candidate({ part_id: 11, part_number: "VP-FF-11" })];
  const value = compare_candidates({ candidates, selectedIds: [10, 11] });

  it("renders the comparison table with unavailable cells", () => {
    const withGap = compare_candidates({
      candidates: [candidate(), candidate({ part_id: 11, source_reference: "" })],
      selectedIds: [10, 11],
    });
    render(<CandidateComparison value={withGap} loading={false} error={null} onAction={vi.fn()} candidates={candidates} selectedIds={[10, 11]} />);
    expect(screen.getByTestId("candidate-comparison")).toBeInTheDocument();
    expect(screen.getAllByText("unavailable").length).toBeGreaterThan(0);
  });

  it("select sends only the candidate id and is keyboard-operable", async () => {
    const onAction = vi.fn().mockResolvedValue(undefined);
    render(<CandidateComparison value={value} loading={false} error={null} onAction={onAction} candidates={candidates} selectedIds={[10, 11]} />);
    const button = screen.getByRole("button", { name: /select #11/i });
    button.focus();
    expect(button).toHaveFocus(); // keyboard focusable (native button)
    await userEvent.keyboard("{Enter}");
    expect(onAction).toHaveBeenCalledWith({ candidates, selectedIds: [11] });
  });

  it("shows empty and loading states", () => {
    const { rerender } = render(<CandidateComparison value={null} loading={false} error={null} onAction={vi.fn()} />);
    expect(screen.getByTestId("comparison-empty")).toBeInTheDocument();
    rerender(<CandidateComparison value={null} loading error={null} onAction={vi.fn()} />);
    expect(screen.getByTestId("comparison-loading")).toBeInTheDocument();
  });
});
