"use client";

import { type JSX } from "react";

import type { ApiError } from "@/lib/api";
import { translate, type F07Request, type F07Result, type Locale } from "@/lib/features/f07_arabic_and_english_interface";

// F07 Locale switcher — toggles en/ar, persisting the preference in a cookie. Switching is a
// client-side locale change (it never navigates or reloads), so the current enquiry id and any
// unsent draft are preserved. An identifier passed in is isolated with <bdi> so it stays
// readable inside RTL text. Submits only the typed preference.
function persistPreference(locale: Locale): void {
  try {
    document.cookie = `locale=${locale}; path=/; max-age=31536000; samesite=lax`;
  } catch {
    // Storage/cookies disabled: the switch still updates the in-memory locale via onAction.
  }
}

export function LocaleSwitcher(props: {
  value: F07Result | null;
  loading: boolean;
  error: ApiError | null;
  onAction: (request: F07Request) => Promise<void>;
  pathname?: string;
  sampleIdentifier?: string;
}): JSX.Element {
  const { value, loading, error, onAction, pathname = "/", sampleIdentifier } = props;
  const current = value?.locale ?? "en";

  async function choose(locale: Locale) {
    persistPreference(locale);
    await onAction({ pathname, preference: locale });
  }

  return (
    <section aria-label="Language" data-testid="locale-switcher">
      <button type="button" aria-pressed={current === "en"} disabled={loading} onClick={() => choose("en")}>
        {translate(current, "locale.english")}
      </button>
      <button type="button" aria-pressed={current === "ar"} disabled={loading} onClick={() => choose("ar")}>
        {translate(current, "locale.arabic")}
      </button>
      {error ? <p role="alert">{error.message}</p> : null}
      {value !== null ? (
        <p data-testid="active-locale" lang={value.locale} dir={value.direction}>
          {value.locale}
          {sampleIdentifier ? (
            <>
              {" "}
              <bdi data-testid="isolated-id">{sampleIdentifier}</bdi>
            </>
          ) : null}
        </p>
      ) : null}
    </section>
  );
}
