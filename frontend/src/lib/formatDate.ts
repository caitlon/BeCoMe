/**
 * Format a date consistently across the app for the given locale.
 *
 * Always spells out the month (e.g. "Jul 18, 2026" for en, "18. 7. 2026"
 * for cs) so the result is never a bare numeric date that reads as DD/MM in
 * one place and MM/DD in another depending on how the locale was passed.
 *
 * @param value - ISO date string or Date instance.
 * @param locale - BCP 47 locale tag, typically `i18n.language`.
 */
export function formatDate(value: string | Date, locale: string): string {
  const date = typeof value === 'string' ? new Date(value) : value;
  return new Intl.DateTimeFormat(locale, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(date);
}
