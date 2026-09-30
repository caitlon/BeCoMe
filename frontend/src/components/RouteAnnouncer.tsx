import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router";

export function RouteAnnouncer() {
  const location = useLocation();
  const [announcement, setAnnouncement] = useState("");
  const previousPathname = useRef<string | null>(null);

  useEffect(() => {
    const previous = previousPathname.current;
    previousPathname.current = location.pathname;

    // A full page load has not navigated anywhere: leave focus on the document so the
    // skip link is still the first Tab stop, and leave the title to the screen reader.
    if (previous === null || previous === location.pathname) return;

    // Scroll to top on navigation
    window.scrollTo(0, 0);

    // Move focus to main content with rAF retry for lazy-loaded routes
    let retries = 0;
    let frameId: number | null = null;
    const focusMain = () => {
      const main = document.getElementById("main-content");
      if (main) {
        if (!main.hasAttribute("tabindex")) {
          main.setAttribute("tabindex", "-1");
        }
        main.focus({ preventScroll: true });
        return;
      }
      /* v8 ignore next 3 */
      if (retries++ < 10) {
        frameId = requestAnimationFrame(focusMain);
      }
    };
    focusMain();

    // Announce page change after a small delay to let the title update
    const timeout = setTimeout(() => {
      setAnnouncement(document.title);
    }, 100);

    return () => {
      if (frameId !== null) cancelAnimationFrame(frameId);
      clearTimeout(timeout);
    };
  }, [location.pathname]);

  return (
    <output
      aria-live="polite"
      aria-atomic="true"
      className="sr-only"
    >
      {announcement}
    </output>
  );
}
