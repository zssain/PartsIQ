"use client";

import { useCallback, useEffect, useState, type JSX } from "react";

import { ApiError } from "@/lib/api";
import { HistoryList } from "@/components/features/HistoryList";
import { listHistory, type F19Request, type F19Result } from "@/lib/features/f19_enquiry_history";

// F19 customer navigation target: the caller's own enquiry history. The first page loads on
// mount; "Load more" appends subsequent cursor pages. Ownership is enforced by the gateway.
export default function HistoryPage(): JSX.Element {
  const [value, setValue] = useState<F19Result | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);

  const run = useCallback(async (request: F19Request) => {
    setLoading(true);
    setError(null);
    try {
      const page = await listHistory(request);
      // Append when paging forward with a cursor; replace on a fresh load.
      setValue((prev) =>
        request.cursor && prev
          ? { enquiries: [...prev.enquiries, ...page.enquiries], next_cursor: page.next_cursor }
          : page,
      );
    } catch (err) {
      setError(err instanceof ApiError ? err : null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void run({});
  }, [run]);

  return (
    <main>
      <h1>Your enquiries</h1>
      <HistoryList value={value} loading={loading && value === null} error={error} onAction={run} />
    </main>
  );
}
