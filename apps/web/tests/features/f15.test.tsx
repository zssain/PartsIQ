// F15 OCR confirmation — show extracted identifiers, confirm/correct, preserve leading zeros.
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { OcrConfirmation } from "@/components/chat/OcrConfirmation";
import type { NameplateResult } from "@/lib/contracts";

function extraction(overrides: Partial<NameplateResult> = {}): NameplateResult {
  return {
    attachment_id: "11111111-1111-4111-8111-111111111111",
    model_text: "VP-20",
    serial_text: "000150",
    issues: [],
    confirmation_required: true,
    ...overrides,
  };
}

describe("OcrConfirmation (F15)", () => {
  it("prefills the extracted fields for confirmation", () => {
    render(<OcrConfirmation extraction={extraction()} extractionId="e1" expectedRevision={2} onConfirm={vi.fn()} />);
    expect((screen.getByLabelText(/model/i) as HTMLInputElement).value).toBe("VP-20");
    expect((screen.getByLabelText(/serial/i) as HTMLInputElement).value).toBe("000150");
  });

  it("confirms with leading zeros preserved and the expected revision", async () => {
    const onConfirm = vi.fn().mockResolvedValue(undefined);
    render(<OcrConfirmation extraction={extraction()} extractionId="e1" expectedRevision={2} onConfirm={onConfirm} />);
    await userEvent.click(screen.getByRole("button", { name: /confirm/i }));
    expect(onConfirm).toHaveBeenCalledWith({
      extraction_id: "e1",
      expected_revision: 2,
      model_text: "VP-20",
      serial_text: "000150",
    });
  });

  it("allows a blank serial (routes to the missing-serial flow)", async () => {
    const onConfirm = vi.fn().mockResolvedValue(undefined);
    render(
      <OcrConfirmation
        extraction={extraction({ serial_text: null })}
        extractionId="e1"
        expectedRevision={1}
        onConfirm={onConfirm}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: /confirm/i }));
    expect(onConfirm).toHaveBeenCalledWith(expect.objectContaining({ serial_text: "" }));
  });

  it("surfaces legibility issues", () => {
    render(
      <OcrConfirmation
        extraction={extraction({ issues: ["glare", "partial_plate"] })}
        extractionId="e1"
        expectedRevision={1}
        onConfirm={vi.fn()}
      />,
    );
    expect(screen.getByText(/hard to read/i)).toBeInTheDocument();
  });
});
