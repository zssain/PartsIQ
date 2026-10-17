"use client";

import { useCallback, useEffect, useState, type JSX } from "react";

import { ApiError } from "@/lib/api";
import { MetricsDashboard } from "@/components/features/MetricsDashboard";
import { metricsDashboard, type F63Request, type F63Result } from "@/lib/features/f63_metrics_dashboard";

// F63 staff analytics page. Loads a 30-day window on mount; demo traffic excluded by default.
// Evaluation accuracy is admin-only (enforced server-side).
export default function AnalyticsPage(): JSX.Element {
  const [value, setValue] = useState<F63Result | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);

  const run = useCallback(async (request: F63Request) => {
    setLoading(true);
    setError(null);
    try {
      setValue(await metricsDashboard(request));
    } catch (err) {
      setError(err instanceof ApiError ? err : null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const end = new Date();
    const start = new Date(end.getTime() - 30 * 24 * 3600 * 1000);
    void run({ start: start.toISOString(), end: end.toISOString() });
  }, [run]);

  return (
    <main>
      <h1>Analytics</h1>
      <MetricsDashboard value={value} loading={loading && value === null} error={error} onAction={run} />
    </main>
  );
}
