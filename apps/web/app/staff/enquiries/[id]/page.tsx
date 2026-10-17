"use client";

import { use, useCallback, useState, type JSX } from "react";

import { ApiError } from "@/lib/api";
import { StockFreshness } from "@/components/features/StockFreshness";
import { Workspace } from "@/components/review/Workspace";
import type { F35Request, F35Result } from "@/lib/features/f35_stock_freshness";

// F35: the reviewer can re-check stock freshness for the enquiry under review. The freshness
// verdict is computed server-side (gateway attaches the verified facts and calls the search
// /internal/stock/check route); the live call is BLOCKED here, so the panel stays empty rather
// than fabricate a fresh/stale result.
export default function StaffEnquiryPage({
  params,
}: {
  params: Promise<{ id: string }>;
}): JSX.Element {
  const { id } = use(params);
  const [freshness, setFreshness] = useState<F35Result | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  const recheck = useCallback(async (_request: F35Request) => {
    setError(null);
    // Server-side freshness check is wired by the gateway/search owners (BLOCKED here).
    setFreshness(null);
  }, []);

  return (
    <main>
      <h1>Review enquiry</h1>
      <StockFreshness
        value={freshness}
        loading={false}
        error={error}
        onAction={recheck}
        enquiryId={id}
        expectedRevision={1}
      />
      <Workspace enquiryId={id} />
    </main>
  );
}
