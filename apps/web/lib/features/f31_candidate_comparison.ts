// F31 Candidate comparison — compare 2-3 candidates from the SAME item/revision (owner web).
//
// Pure, browser-side presentation only: it reshapes server-provided CandidateView rows into a
// comparison table (number, names, evidence, availability). It authors no compatibility facts —
// a missing attribute is surfaced as `null` (shown "unavailable"), never invented. Selecting a
// candidate submits only its id. A foreign candidate (not in this item's set) or candidates
// from mixed items/revisions are rejected.

import type { CandidateView } from "@/lib/contracts";

export interface ComparisonRow {
  attribute: string;
  values: (string | null)[];
}

export interface F31Request {
  candidates: CandidateView[];
  selectedIds: number[];
}

export interface F31Result {
  rows: ComparisonRow[];
}

function availability(candidate: CandidateView): string | null {
  if (!candidate.stock || candidate.stock.length === 0) return null;
  const total = candidate.stock.reduce((sum, level) => sum + Number(level.available), 0);
  return String(total);
}

export function compare_candidates(request: F31Request): F31Result {
  const { candidates, selectedIds } = request;
  if (selectedIds.length < 2 || selectedIds.length > 3) {
    throw new Error("compare two or three candidates");
  }
  const selected = selectedIds.map((id) => {
    const found = candidates.find((candidate) => candidate.part_id === id);
    if (!found) throw new Error("foreign candidate"); // not part of this item's candidate set
    return found;
  });
  const { item_id, revision } = selected[0];
  for (const candidate of selected) {
    if (candidate.item_id !== item_id || candidate.revision !== revision) {
      throw new Error("candidates must share the same item and revision");
    }
  }
  const rows: ComparisonRow[] = [
    { attribute: "Part number", values: selected.map((c) => c.part_number || null) },
    { attribute: "Name (EN)", values: selected.map((c) => c.name_en || null) },
    { attribute: "Name (AR)", values: selected.map((c) => c.name_ar || null) },
    { attribute: "Evidence", values: selected.map((c) => c.source_reference || null) },
    { attribute: "Availability", values: selected.map(availability) },
  ];
  return { rows };
}
