import { useLayoutEffect } from "react";

/**
 * Removes the `lang-pending` class from `<html>` once React has committed its first render.
 *
 * The pre-paint script in `index.html` adds the class for Czech visitors, and `index.css`
 * hides `#root` while it is set. The prerendered pages are English, and the client entry will
 * hydrate them for English visitors but mount fresh with `createRoot` for Czech ones, so until
 * React commits, a Czech visitor would see English text. A layout effect runs after the commit
 * and before the browser paints it, so the page appears already in Czech. Removing a class that
 * is not there does nothing.
 */
export function RevealOnCommit({ children }: { readonly children: React.ReactNode }) {
  useLayoutEffect(() => {
    document.documentElement.classList.remove("lang-pending");
  }, []);

  return children;
}
