"use client";

import { useRouter } from "next/navigation";
import { useState, type JSX } from "react";

import type { Locale } from "@/lib/features/f07_arabic_and_english_interface";

// Compact EN / العربية toggle. Persists the preference cookie (F07) and refreshes the route so
// the server layout re-reads it and flips <html lang/dir> — no full reload, draft state survives.
export function LocaleControl({ initial = "en" }: { initial?: Locale }): JSX.Element {
  const router = useRouter();
  const [locale, setLocale] = useState<Locale>(initial);

  function choose(next: Locale) {
    setLocale(next);
    try {
      document.cookie = `locale=${next}; path=/; max-age=31536000; samesite=lax`;
      document.documentElement.setAttribute("lang", next);
      document.documentElement.setAttribute("dir", next === "ar" ? "rtl" : "ltr");
    } catch {
      /* cookies disabled: still flips in-memory */
    }
    router.refresh();
  }

  return (
    <div className="pq-badge" role="group" aria-label="Language" style={{ padding: "0.25rem", gap: "0.15rem" }}>
      <button
        type="button"
        onClick={() => choose("en")}
        aria-pressed={locale === "en"}
        className="pq-chip"
        style={{ background: locale === "en" ? "var(--pq-grad-brand)" : "transparent", color: locale === "en" ? "#1a1405" : "inherit", border: "none" }}
      >
        EN
      </button>
      <button
        type="button"
        onClick={() => choose("ar")}
        aria-pressed={locale === "ar"}
        className="pq-chip"
        style={{ background: locale === "ar" ? "var(--pq-grad-brand)" : "transparent", color: locale === "ar" ? "#1a1405" : "inherit", border: "none" }}
      >
        ع
      </button>
    </div>
  );
}
