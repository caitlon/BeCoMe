/**
 * A source link may be clickable only when it is an https URL written out as
 * `https://` (lower case, no leading space). Everything else (javascript:, data:,
 * http:, `https:foo.com`, `HTTPS://x`, a relative path the model might invent, a
 * non-string that came out of hand-edited storage) is rejected, so the caller
 * falls back to plain text.
 */
export function isAllowedAssistantUrl(url: unknown): boolean {
  if (typeof url !== "string" || !url.startsWith("https://")) return false;
  try {
    return new URL(url).protocol === "https:";
  } catch {
    return false;
  }
}
