"use client";

import { useState, type JSX } from "react";

import type { ApiError } from "@/lib/api";
import type { F57Request, F57Result } from "@/lib/features/f57_catalogue_browser";

// F57 Catalogue browser — filter the active published catalogue by text/model/category and
// page through results; each row shows supersession, and staff can open fitment/sources. The
// form submits only typed filter identifiers. States: loading / empty / error / success.
export function CatalogueBrowser(props: {
  value: F57Result | null;
  loading: boolean;
  error: ApiError | null;
  onAction: (request: F57Request) => Promise<void>;
}): JSX.Element {
  const { value, loading, error, onAction } = props;
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");

  async function search(event: React.FormEvent) {
    event.preventDefault();
    await onAction({ query: query || null, category: category || null });
  }

  async function loadMore() {
    if (value?.next_cursor) await onAction({ query: query || null, category: category || null, cursor: value.next_cursor });
  }

  return (
    <section aria-label="Catalogue browser" data-testid="catalogue-browser">
      <form onSubmit={search}>
        <label>
          Search
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Part number or name" />
        </label>
        <label>
          Category
          <input value={category} onChange={(e) => setCategory(e.target.value)} />
        </label>
        <button type="submit" disabled={loading}>
          Search
        </button>
      </form>

      {loading ? <p data-testid="catalogue-loading">Searching the catalogue…</p> : null}
      {error ? (
        <p role="alert">
          {error.message}
          {error.requestId ? ` (ref ${error.requestId})` : ""}
        </p>
      ) : null}
      {value === null && !loading && !error ? (
        <p data-testid="catalogue-empty">Search the published catalogue to begin.</p>
      ) : null}
      {value !== null ? (
        value.parts.length === 0 ? (
          <p data-testid="catalogue-empty">No parts match those filters.</p>
        ) : (
          <>
            <ul>
              {value.parts.map((part) => (
                <li key={part.id} data-category={part.category}>
                  <strong>{part.part_number}</strong> — {part.name_en}
                  {part.superseded_by ? <em> (superseded by {part.superseded_by})</em> : null}
                </li>
              ))}
            </ul>
            {value.next_cursor ? (
              <button type="button" onClick={loadMore} disabled={loading}>
                Load more
              </button>
            ) : null}
          </>
        )
      ) : null}
    </section>
  );
}
