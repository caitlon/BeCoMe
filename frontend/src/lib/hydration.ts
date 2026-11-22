import type { SupportedLanguage } from "@/i18n";

/**
 * Whether this page load started from server-rendered HTML that React hydrates.
 *
 * The prerendered pages are English, signed out and in the default theme, so a
 * component that reads browser state (a stored theme, the system colour scheme)
 * must start from what the server saw while this is true, then correct itself
 * inside startTransition. The client entry sets the flag right before
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
 * Whether the client entry should hydrate the root element instead of mounting
 * a fresh tree. Only English visitors hydrate: the prerendered HTML is English,
 * so a Czech visitor would get a language mismatch, and a fresh render replaces
 * it before the first paint instead. An empty root is a page with no prerendered
 * HTML, such as the shell served for the routes behind a login.
 */
export function shouldHydrate(rootElement: Element, language: SupportedLanguage): boolean {
  return rootElement.childElementCount > 0 && language === "en";
}
