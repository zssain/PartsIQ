// Preserve-unsent-input on a failed send (customer chat composer).
// A recoverable send failure must NOT clear the textarea — the customer never loses their words;
// a confirmed send clears it. Also verifies the FixtureBanner renders in the fixture demo.
import { render, screen, waitFor } from "@testing-library/react";
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

import { Chat } from "@/components/chat/Chat";
import { FixtureBanner } from "@/components/visibility/FixtureBanner";
import { ApiError } from "@/lib/api";
import type { EnquiryView } from "@/lib/contracts";

function enquiry(): EnquiryView {
  return {
    id: "e1", revision: 1, status: "processing", messages: [], item_ids: [],
    catalogue_version_id: null, updated_at: "2026-10-19T12:00:00Z",
  };
}

describe("Preserve unsent input", () => {
  beforeEach(() => apiMock.mockReset());

  it("keeps the composer text when a send fails, and clears it only on a confirmed send", async () => {
    // First call: the poll that loads the enquiry. Subsequent calls: the message POSTs.
    apiMock.mockResolvedValueOnce(enquiry()); // initial poll
    render(<Chat enquiryId="e1" />);

    const textarea = await screen.findByPlaceholderText(/describe the part/i);
    await userEvent.type(textarea, "need a fuel filter");

    // A recoverable failure on send: the text must remain.
    apiMock.mockRejectedValueOnce(new ApiError("DEPENDENCY_UNAVAILABLE", 503, "offline", "req-1"));
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    await screen.findByRole("alert");
    expect((textarea as HTMLTextAreaElement).value).toBe("need a fuel filter"); // preserved

    // A confirmed send clears the composer.
    apiMock.mockResolvedValueOnce({ id: "m1", enquiry_id: "e1", revision: 1, kind: "customer", body: "need a fuel filter", created_at: "t" });
    await userEvent.click(screen.getByRole("button", { name: /send/i }));
    await waitFor(() => expect((textarea as HTMLTextAreaElement).value).toBe(""));
  });

  it("renders the honest fixture banner", () => {
    render(<FixtureBanner />);
    expect(screen.getByTestId("fixture-banner")).toHaveTextContent(/synthetic data, no live providers/i);
  });
});
