"use client";

import { useCallback, useEffect, useState, type JSX } from "react";

import { ApiError } from "@/lib/api";
import { InboxFilters } from "@/components/features/InboxFilters";
import { listInbox, type F36Request, type F36Result } from "@/lib/features/f36_staff_inbox";

// Staff inbox (prompt 20 shell, F36 filters/scope/counts). Lists the enquiries the signed-in
// reviewer may act on (assigned-only for real enquiries; own session for demo — enforced
// server-side); an admin sees all. Counts are within the access scope.
export default function InboxPage(): JSX.Element {
  const [value, setValue] = useState<F36Result | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);

  const run = useCallback(async (request: F36Request) => {
    setLoading(true);
    setError(null);
    try {
      setValue(await listInbox(request));
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
      <h1>Review inbox</h1>
      <InboxFilters value={value} loading={loading && value === null} error={error} onAction={run} />
    </main>
  );
}
