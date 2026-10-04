import { useLayoutEffect, useRef } from "react";

import { PageSpinner } from "@/components/PageSpinner";

/**
 * The placeholder shown while a route or the session check loads. It is a
 * `main#main-content` so the skip link has a target from the first render.
 *
 * If the skip link put focus here and the placeholder is then replaced, the
 * focused element leaves the DOM and focus would fall to <body>. Focus moves
 * to the new main instead, but only when the placeholder held it.
 */
export function PageLoader() {
  const ref = useRef<HTMLElement>(null);

  // A layout effect, because its cleanup runs before the placeholder is removed,
  // while `document.activeElement` still points at it.
  useLayoutEffect(() => {
    const placeholder = ref.current;
    // Suspense hides content it has already shown instead of removing it, and runs this
    // cleanup when it does. A hidden placeholder is no target for the skip link, and its
    // id would come ahead of the visible main's, so it gives the id up and takes it back
    // if it is shown again (React does not reapply an id that has not changed).
    placeholder?.setAttribute("id", "main-content");
    return () => {
      const hadFocus = document.activeElement === placeholder;
      placeholder?.removeAttribute("id");
      if (!hadFocus) return;
      // The replacement is inserted after this cleanup, in the same commit.
      requestAnimationFrame(() => {
        // Focus that has gone somewhere else in the meantime belongs to the user.
        // A placeholder hidden rather than removed keeps it until the next frame.
        const active = document.activeElement;
        if (active !== document.body && active !== placeholder) return;
        document.getElementById("main-content")?.focus({ preventScroll: true });
      });
    };
  }, []);

  return (
    <main
      ref={ref}
      id="main-content"
      tabIndex={-1}
      className="min-h-screen flex items-center justify-center"
    >
      <PageSpinner />
    </main>
  );
}
