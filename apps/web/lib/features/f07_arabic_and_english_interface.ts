// F07 Arabic and English interface (owner: web).
//
// Pure locale resolution + a strict translator. A stored preference wins; otherwise English is
// the default. Direction is derived (Arabic -> rtl). The translator throws on a missing key so a
// missing translation fails tests rather than shipping a blank string. Identifiers (serials,
// part numbers) are isolated with <bdi> at render so they stay readable inside Arabic (RTL)
// text — handled by components; this module owns the pure rules.

import ar from "@/messages/ar.json";
import en from "@/messages/en.json";

export type Locale = "en" | "ar";
export type Direction = "ltr" | "rtl";

export interface F07Request {
  pathname: string;
  preference: Locale | null;
}

export interface F07Result {
  locale: Locale;
  direction: Direction;
}

export const catalogs: Record<Locale, Record<string, string>> = { en, ar };

export function resolve_locale(request: F07Request): F07Result {
  // A persisted preference wins; English is the default. (Path-based detection could use
  // pathname later, but the preference cookie is authoritative here.)
  const locale: Locale = request.preference === "ar" ? "ar" : "en";
  return { locale, direction: locale === "ar" ? "rtl" : "ltr" };
}

export function localeFromCookie(value: string | null): Locale {
  return value === "ar" ? "ar" : "en";
}

export function translate(locale: Locale, key: string): string {
  const message = catalogs[locale][key];
  if (message === undefined) {
    throw new Error(`missing translation for "${key}" in ${locale}`);
  }
  return message;
}
