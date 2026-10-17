"use client";

import { type JSX } from "react";

import type { ApiError } from "@/lib/api";
import type { CandidateView } from "@/lib/contracts";
import type { F31Request, F31Result } from "@/lib/features/f31_candidate_comparison";

// F31 Candidate comparison — side-by-side table of 2-3 candidates. A missing attribute is shown
// "unavailable" (never invented). Each candidate has a Select button (a native, keyboard-operable
// button) that submits only its id — never a browser-authored compatibility fact. States:
// loading / empty / error / success.
export function CandidateComparison(props: {
  value: F31Result | null;
  loading: boolean;
  error: ApiError | null;
  onAction: (request: F31Request) => Promise<void>;
  candidates?: CandidateView[];
  selectedIds?: number[];
}): JSX.Element {
  const { value, loading, error, onAction, candidates = [], selectedIds = [] } = props;

  async function select(partId: number) {
    // Send the chosen candidate id only; the server re-derives facts from it.
    await onAction({ candidates, selectedIds: [partId] });
  }

  if (loading) return <p data-testid="comparison-loading">Comparing candidates…</p>;
  if (error)
    return (
      <p role="alert">
        {error.message}
        {error.requestId ? ` (ref ${error.requestId})` : ""}
      </p>
    );
  if (value === null) return <p data-testid="comparison-empty">Select two or three candidates to compare.</p>;

  const columnIds = selectedIds;
  return (
    <section aria-label="Candidate comparison" data-testid="candidate-comparison">
      <table>
        <thead>
          <tr>
            <th scope="col">Attribute</th>
            {columnIds.map((id) => (
              <th scope="col" key={id}>
                #{id}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {value.rows.map((row) => (
            <tr key={row.attribute}>
              <th scope="row">{row.attribute}</th>
              {row.values.map((cell, index) => (
                <td key={`${row.attribute}-${columnIds[index] ?? index}`} data-unavailable={cell === null}>
                  {cell ?? "unavailable"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <div role="group" aria-label="Choose a candidate">
        {columnIds.map((id) => (
          <button type="button" key={id} onClick={() => select(id)}>
            Select #{id}
          </button>
        ))}
      </div>
    </section>
  );
}
