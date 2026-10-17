"use client";

import { useCallback, useState, type JSX } from "react";

import { ApiError } from "@/lib/api";
import { CatalogueBrowser } from "@/components/features/CatalogueBrowser";
import { browseCatalogue, type F57Request, type F57Result } from "@/lib/features/f57_catalogue_browser";

// F57 staff route: browse the active published catalogue. Pages append when a cursor is passed.
export default function StaffCataloguePage(): JSX.Element {
  const [value, setValue] = useState<F57Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const run = useCallback(async (request: F57Request) => {
    setLoading(true);
    setError(null);
    try {
      const page = await browseCatalogue(request);
      setValue((prev) =>
        request.cursor && prev
          ? { ...page, parts: [...prev.parts, ...page.parts] }
          : page,
      );
    } catch (err) {
      setError(err instanceof ApiError ? err : null);
    } finally {
      setLoading(false);
    }
  }, []);

  return (
    <main>
      <h1>Catalogue</h1>
      <CatalogueBrowser value={value} loading={loading} error={error} onAction={run} />
    </main>
  );
}
