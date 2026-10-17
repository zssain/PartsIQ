// F07 Arabic/English interface — locale resolution, complete catalogs, dir, bdi isolation,
// and a switch that preserves an unsent draft.
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { LocaleSwitcher } from "@/components/features/LocaleSwitcher";
import {
  catalogs,
  resolve_locale,
  translate,
  type F07Request,
  type F07Result,
} from "@/lib/features/f07_arabic_and_english_interface";

describe("resolve_locale + catalogs (F07)", () => {
  it("defaults to English LTR and honors an Arabic preference as RTL", () => {
    expect(resolve_locale({ pathname: "/", preference: null })).toEqual({ locale: "en", direction: "ltr" });
    expect(resolve_locale({ pathname: "/", preference: "ar" })).toEqual({ locale: "ar", direction: "rtl" });
  });

  it("has identical keys in en and ar (a missing translation fails)", () => {
    expect(Object.keys(catalogs.en).sort()).toEqual(Object.keys(catalogs.ar).sort());
    for (const key of Object.keys(catalogs.en)) {
      expect(catalogs.ar[key]?.length ?? 0).toBeGreaterThan(0);
    }
  });

  it("throws on a missing translation key", () => {
    expect(() => translate("ar", "does.not.exist")).toThrow(/missing translation/i);
  });
});

describe("LocaleSwitcher (F07)", () => {
  it("isolates an identifier with bdi and sets dir on the active locale", () => {
    const value: F07Result = { locale: "ar", direction: "rtl" };
    render(<LocaleSwitcher value={value} loading={false} error={null} onAction={vi.fn()} sampleIdentifier="VP-FF-10" />);
    const id = screen.getByTestId("isolated-id");
    expect(id.tagName.toLowerCase()).toBe("bdi");
    expect(id).toHaveTextContent("VP-FF-10");
    expect(screen.getByTestId("active-locale").getAttribute("dir")).toBe("rtl");
  });

  it("switching language preserves an unsent draft (no reload/unmount)", async () => {
    const onAction = vi.fn().mockResolvedValue(undefined);
    function Harness() {
      const [draft, setDraft] = useState("");
      const [value, setValue] = useState<F07Result | null>({ locale: "en", direction: "ltr" });
      return (
        <div>
          <input aria-label="draft" value={draft} onChange={(e) => setDraft(e.target.value)} />
          <LocaleSwitcher
            value={value}
            loading={false}
            error={null}
            onAction={async (req: F07Request) => {
              await onAction(req);
              setValue(resolve_locale(req));
            }}
          />
        </div>
      );
    }
    render(<Harness />);
    const input = screen.getByLabelText("draft");
    await userEvent.type(input, "need a fuel filter");
    await userEvent.click(screen.getByRole("button", { name: /العربية/ }));
    expect(onAction).toHaveBeenCalledWith({ pathname: "/", preference: "ar" });
    expect((input as HTMLInputElement).value).toBe("need a fuel filter"); // draft preserved across switch
    expect(screen.getByTestId("active-locale").getAttribute("dir")).toBe("rtl");
  });
});
