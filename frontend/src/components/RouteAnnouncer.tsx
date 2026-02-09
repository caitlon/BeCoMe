import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";

export function RouteAnnouncer() {
  const location = useLocation();
  const [announcement, setAnnouncement] = useState("");
  const previousPathname = useRef<string | null>(null);

  useEffect(() => {
    if (previousPathname.current !== null && location.pathname === previousPathname.current) return;
    previousPathname.current = location.pathname;

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
    <div
      aria-live="polite"
      aria-atomic="true"
      role="status"
      className="sr-only"
    >
      {announcement}
    </div>
  );
}
