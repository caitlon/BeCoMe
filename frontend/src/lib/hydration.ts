import type { SupportedLanguage } from "@/i18n";

/**
 * Whether this page load started from server-rendered HTML that React hydrates.
 *
 * The prerendered pages are English, signed out and in the default theme, so a
 * component that reads browser state (a stored theme, the system colour scheme)
 * must start from what the server saw while this is true, then correct itself
 * inside startTransition. mountApp sets the flag right before
 * hydrateRoot and never clears it: it says how the page load began, not
 * whether hydration has finished, and ThemeProvider reads it once, at mount.
 * Nothing sets it on the createRoot path, which keeps its current behavior.
 */
let hydrating = false;

export function isHydrating(): boolean {
  return hydrating;
}

export function setHydrating(value: boolean): void {
  hydrating = value;
}

/**
 * Whether mountApp should hydrate the root element instead of mounting a fresh
 * tree. Only English visitors hydrate: the prerendered HTML is English, so a
 * Czech visitor would get a language mismatch, and a fresh render replaces it
 * before the first paint instead.
 *
 * The root also has to carry the route it was rendered for (`data-route`, which
 * prerender.mjs writes) and that route has to be the one the browser is on. nginx
 * serves the 404 page at any unknown path, and an unknown case-study id has a
 * route of its own that renders something else than the 404 page, so server
 * markup for a different route would not match what the client router renders.
 * An empty root (the shell served for the routes behind a login) and the 404
 * page, which has no `data-route`, mount fresh.
 *
 * @param pathname - The current location's path; a trailing slash is ignored.
 */
export function shouldHydrate(
  rootElement: HTMLElement,
  language: SupportedLanguage,
  pathname: string,
): boolean {
  return (
    rootElement.childElementCount > 0 &&
    language === "en" &&
    rootElement.dataset.route === withoutTrailingSlash(pathname)
  );
}

/** The path with its trailing slashes removed; the root path stays "/". */
function withoutTrailingSlash(pathname: string): string {
  let end = pathname.length;
  while (end > 1 && pathname[end - 1] === "/") end--;
  return pathname.slice(0, end);
}
