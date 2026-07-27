import type { Breadcrumb, ErrorEvent } from "@sentry/react";

/**
 * Query parameters that carry a credential and must never reach the error tracker.
 *
 * The password-reset link is the live case: `/reset-password?token=<raw token>` is
 * redeemable until it is used, and both the event's request URL and the navigation
 * breadcrumbs would otherwise carry it verbatim.
 */
const SENSITIVE_PARAMS = ["token", "access_token", "refresh_token"];

const REDACTED = "[redacted]";

/**
 * Replace the value of every credential-bearing query parameter in a URL.
 *
 * Relative URLs are preserved as relative; anything unparseable is returned as-is,
 * since a scrubber must never be the reason an event fails to send.
 */
export function scrubUrl(raw: string): string {
  let parsed: URL;
  try {
    parsed = new URL(raw, "http://placeholder.invalid");
  } catch {
    return raw;
  }

  const present = SENSITIVE_PARAMS.filter((name) => parsed.searchParams.has(name));
  if (present.length === 0) return raw;

  for (const name of present) {
    parsed.searchParams.set(name, REDACTED);
  }

  const isAbsolute = /^[a-z][a-z0-9+.-]*:/i.test(raw);
  return isAbsolute ? parsed.toString() : `${parsed.pathname}${parsed.search}${parsed.hash}`;
}

/** Strip credentials from the URL an event reports. */
export function scrubEvent(event: ErrorEvent): ErrorEvent {
  if (event.request?.url) {
    event.request.url = scrubUrl(event.request.url);
  }
  return event;
}

/**
 * Strip credentials from a breadcrumb.
 *
 * Navigation crumbs keep the URLs under `data.from` / `data.to`; fetch and xhr
 * crumbs keep the request URL under `data.url`.
 */
export function scrubBreadcrumb(breadcrumb: Breadcrumb): Breadcrumb {
  const data = breadcrumb.data;
  if (!data) return breadcrumb;

  for (const key of ["from", "to", "url"]) {
    const value = data[key];
    if (typeof value === "string") {
      data[key] = scrubUrl(value);
    }
  }
  return breadcrumb;
}
