/**
 * A source link may be clickable only when it is an https URL. Everything else
 * (javascript:, data:, http:, a relative path the model might invent, a
 * non-string that came out of hand-edited storage) is rejected, so the caller
 * falls back to plain text.
 */
export function isAllowedAssistantUrl(url: unknown): boolean {
  if (typeof url !== "string") return false;
  try {
    return new URL(url).protocol === "https:";
  } catch {
    return false;
  }
}
