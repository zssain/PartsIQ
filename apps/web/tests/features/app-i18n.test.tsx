// Workspace dictionary (lib/app-i18n.tsx): Arabic must cover every English key with a real
// translation, placeholders must survive translation, and the helpers must interpolate without
// breaking word order or dropping identifiers.
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { APP_DICTIONARIES, AppLocaleProvider, translate, useLabel, useTx } from "@/lib/app-i18n";

// Values that are legitimately the same in both languages (brand names, identifiers, symbols).
const SAME_IN_BOTH = new Set<string>([]);

const placeholders = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort();

describe("workspace dictionary", () => {
  const en = APP_DICTIONARIES.en;
  const ar = APP_DICTIONARIES.ar;

  it("has exactly the same key set in English and Arabic", () => {
    expect(Object.keys(ar).sort()).toEqual(Object.keys(en).sort());
  });

  it("has no empty Arabic value and none left identical to English (outside the allowlist)", () => {
    for (const key of Object.keys(en) as (keyof typeof en)[]) {
      expect(ar[key].trim(), key).not.toBe("");
      if (!SAME_IN_BOTH.has(key)) expect(ar[key], key).not.toBe(en[key]);
    }
  });

  it("keeps every placeholder in the Arabic template", () => {
    for (const key of Object.keys(en) as (keyof typeof en)[]) {
      expect(placeholders(ar[key]), key).toEqual(placeholders(en[key]));
    }
  });

  it("keeps the product name Latin", () => {
    expect(ar["entry.signinBody"]).toContain("PartsIQ");
    expect(ar["shell.home"]).toContain("PartsIQ");
  });

  it("interpolates plain values", () => {
    expect(translate("en", "pager.many", { count: 7 })).toBe("7 results");
    expect(translate("ar", "pager.range", { from: 1, to: 20, total: 45 })).toBe("1–20 من 45");
  });
});

describe("rich interpolation and server codes", () => {
  function Sample({ code }: { code: string }) {
    const tx = useTx();
    const label = useLabel();
    return (
      <>
        <p data-testid="rich">{tx("detail.compatiblePart", { part: <bdi data-testid="part">CA-AF-8973</bdi>, name: "Air filter" })}</p>
        <p data-testid="code">{label("runStatus", code)}</p>
        <p data-testid="server">{label("participant", "intake", "Intake specialist")}</p>
      </>
    );
  }

  it("isolates identifiers inside Arabic sentences and keeps Arabic word order", () => {
    render(<AppLocaleProvider locale="ar"><Sample code="paused" /></AppLocaleProvider>);
    const part = screen.getByTestId("part");
    expect(part.tagName.toLowerCase()).toBe("bdi");
    expect(screen.getByTestId("rich").textContent).toBe("القطعة المتوافقة CA-AF-8973 — Air filter");
    expect(screen.getByTestId("code")).toHaveTextContent("متوقف مؤقتًا");
    expect(screen.getByTestId("server")).toHaveTextContent("متخصص الاستلام");
  });

  it("uses the server label in English and falls back to the raw code when unknown", () => {
    render(<AppLocaleProvider locale="en"><Sample code="brand_new_status" /></AppLocaleProvider>);
    expect(screen.getByTestId("rich").textContent).toBe("Compatible part CA-AF-8973 — Air filter");
    expect(screen.getByTestId("code")).toHaveTextContent("brand_new_status");
    expect(screen.getByTestId("server")).toHaveTextContent("Intake specialist");
  });
});
