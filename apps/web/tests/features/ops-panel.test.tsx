// OpsPanel visibility panel — measured operations metrics or an HONEST offline empty state.
// Covers: loading→data (stage latency, token usage, retries, remaining allowance), the honest
// offline/role-denied empty state (NO fabricated numbers), unmeasured fields, error+retry.
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const apiMock = vi.fn();
vi.mock("@/lib/api", () => ({
  api: (...args: unknown[]) => apiMock(...args),
  ApiError: class ApiError extends Error {
    code: string;
    status: number;
    requestId: string | null;
    constructor(code: string, status: number, message: string, requestId: string | null) {
      super(message);
      this.code = code;
      this.status = status;
      this.requestId = requestId;
    }
  },
}));

import { OpsPanel } from "@/components/visibility/OpsPanel";
import { ApiError } from "@/lib/api";
import type { OpsMetrics } from "@/lib/live";

function metrics(): OpsMetrics {
  return {
    stages: [
      { stage: "identify", p50_ms: 120, p95_ms: 240 },
      { stage: "verify", p50_ms: 30, p95_ms: 55 },
    ],
    tokens_used: 1840,
    retries: 2,
    remaining_allowance: 500,
    updated_at: "2026-10-19T12:00:00Z",
  };
}

describe("OpsPanel", () => {
  beforeEach(() => apiMock.mockReset());

  it("goes loading → data and shows stage latency, tokens, retries and remaining allowance", async () => {
    apiMock.mockResolvedValue(metrics());
    render(<OpsPanel />);

    expect(screen.getByTestId("ops-loading")).toBeInTheDocument();

    expect(await screen.findByTestId("ops-tokens")).toHaveTextContent("1840");
    expect(screen.getByTestId("ops-retries")).toHaveTextContent("2");
    expect(screen.getByTestId("ops-allowance")).toHaveTextContent("500");
    const stages = screen.getByTestId("ops-stages");
    expect(stages).toHaveTextContent("identify");
    expect(stages).toHaveTextContent("p95 240 ms");
  });

  it("reads 'not measured' for unmeasured fields instead of fabricating a zero", async () => {
    apiMock.mockResolvedValue({ stages: [], tokens_used: null, retries: null, remaining_allowance: null, updated_at: null } satisfies OpsMetrics);
    render(<OpsPanel />);
    expect(await screen.findByTestId("ops-tokens")).toHaveTextContent("not measured");
    expect(screen.getByTestId("ops-retries")).toHaveTextContent("not measured");
    expect(screen.getByTestId("ops-allowance")).toHaveTextContent("not measured");
    expect(screen.getByTestId("ops-stages-empty")).toBeInTheDocument();
  });

  it("shows the HONEST offline empty state on 403 with no fabricated numbers", async () => {
    apiMock.mockRejectedValueOnce(new ApiError("FORBIDDEN", 403, "forbidden", "req-403"));
    render(<OpsPanel />);
    const empty = await screen.findByTestId("ops-empty");
    expect(empty).toHaveTextContent(/signed-in staff session/i);
    expect(empty).toHaveTextContent(/live backend/i);
    expect(empty).toHaveTextContent("req-403");
    // no fabricated metric values anywhere.
    expect(screen.queryByTestId("ops-tokens")).toBeNull();
    expect(screen.queryByTestId("ops-stages")).toBeNull();
    expect(empty.textContent).not.toMatch(/\d+\s?ms/);
  });

  it("shows the honest offline empty state when the backend is unavailable (503)", async () => {
    apiMock.mockRejectedValueOnce(new ApiError("DEPENDENCY_UNAVAILABLE", 503, "offline", "req-503"));
    render(<OpsPanel />);
    expect(await screen.findByTestId("ops-empty")).toHaveTextContent(/live backend/i);
  });

  it("shows an error with request id and retries on a transient 500", async () => {
    apiMock.mockRejectedValueOnce(new ApiError("DEPENDENCY_UNAVAILABLE", 500, "boom", "req-500"));
    render(<OpsPanel />);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("boom");
    expect(alert).toHaveTextContent("req-500");

    apiMock.mockResolvedValueOnce(metrics());
    await userEvent.click(screen.getByTestId("ops-retry"));
    expect(await screen.findByTestId("ops-tokens")).toHaveTextContent("1840");
  });
});
