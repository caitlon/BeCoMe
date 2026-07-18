import * as React from "react";

/**
 * Track whether a CSS media query matches the current viewport.
 *
 * Subscribes to the browser MediaQueryList and re-renders whenever the match
 * state flips. This lets a component render a single layout for the active
 * breakpoint instead of mounting every variant and hiding the rest with CSS,
 * which would duplicate the DOM and leave hidden form fields owning input refs.
 *
 * Returns false in environments without matchMedia. The app is a client-only
 * Vite SPA with no server rendering, so a real matchMedia is present on the
 * first browser render and the fallback only guards non-DOM runtimes.
 *
 * @param query - Media query string, for example "(min-width: 1024px)".
 * @returns true while the query matches the viewport.
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = React.useState<boolean>(() => queryMatches(query));

  React.useEffect(() => {
    if (typeof globalThis.matchMedia !== "function") return;
    const mediaQuery = globalThis.matchMedia(query);
    const onChange = () => setMatches(mediaQuery.matches);
    mediaQuery.addEventListener("change", onChange);
    // eslint-disable-next-line react-hooks/set-state-in-effect -- re-sync after mount in case the viewport (or the query) changed between render and effect
    setMatches(mediaQuery.matches);
    return () => mediaQuery.removeEventListener("change", onChange);
  }, [query]);

  return matches;
}

function queryMatches(query: string): boolean {
  if (typeof globalThis.matchMedia !== "function") {
    return false;
  }
  return globalThis.matchMedia(query).matches;
}
