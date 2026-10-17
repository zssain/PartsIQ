// F07 i18n request helper: resolve the active locale from the preference cookie and load its
// message catalog. Plain module (no new i18n package) — the catalogs are the single source of
// translated strings.

import { catalogs, localeFromCookie, resolve_locale, type Locale } from "@/lib/features/f07_arabic_and_english_interface";

export function getMessages(locale: Locale): Record<string, string> {
  return catalogs[locale];
}

export function requestLocale(cookieValue: string | null, pathname = "/"): { locale: Locale; direction: "ltr" | "rtl" } {
  const preference = cookieValue ? localeFromCookie(cookieValue) : null;
  return resolve_locale({ pathname, preference });
}
