import * as React from "react";

/**
 * Track whether a CSS media query matches the current viewport.
 *
 * Subscribes to the browser MediaQueryList through useSyncExternalStore and
 * re-renders whenever the match state flips. This lets a component render a
 * single layout for the active breakpoint instead of mounting every variant
 * and hiding the rest with CSS, which would duplicate the DOM and leave hidden
 * form fields owning input refs.
 *
 * Reading through an external store, rather than mirroring the match into
 * useState from an effect, keeps the value correct on the very first render and
 * avoids a synchronous setState inside an effect. Returns false in environments
 * without matchMedia: the app is a client-only Vite SPA with no server
 * rendering, so the fallback only guards non-DOM runtimes.
 *
 * @param query - Media query string, for example "(min-width: 1024px)".
 * @returns true while the query matches the viewport.
 */
export function useMediaQuery(query: string): boolean {
  const subscribe = React.useCallback(
    (onStoreChange: () => void) => {
      if (typeof globalThis.matchMedia !== "function") return () => {};
      const mediaQuery = globalThis.matchMedia(query);
      mediaQuery.addEventListener("change", onStoreChange);
      return () => mediaQuery.removeEventListener("change", onStoreChange);
    },
    [query],
  );

  return React.useSyncExternalStore(
    subscribe,
    () => queryMatches(query),
    () => false,
  );
}

function queryMatches(query: string): boolean {
  if (typeof globalThis.matchMedia !== "function") {
    return false;
  }
  return globalThis.matchMedia(query).matches;
}
