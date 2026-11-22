import type { ReactNode } from "react";
import { createRoot, hydrateRoot } from "react-dom/client";
import * as Sentry from "@sentry/react";
import type { SupportedLanguage } from "@/i18n";
import { setHydrating, shouldHydrate } from "@/lib/hydration";
import { logger } from "@/lib/logger";

/**
 * Mounts the app into the root element: hydrates the prerendered HTML for an
 * English visitor on the route it was rendered for and renders a fresh tree
 * otherwise (see shouldHydrate).
 *
 * The hydrating flag is set before hydrateRoot so that ThemeProvider, which reads
 * it once at mount, starts from what the server rendered.
 */
export function mountApp(rootElement: HTMLElement, tree: ReactNode, language: SupportedLanguage): void {
  if (shouldHydrate(rootElement, language, window.location.pathname)) {
    setHydrating(true);
    hydrateRoot(rootElement, tree, {
      // A callback makes Sentry record the error as handled. Without one, a recoverable
      // hydration error (a browser extension or a page translator changing the DOM)
      // counts as a crash in release health, and React's default console report is lost.
      onRecoverableError: Sentry.reactErrorHandler((error) => {
        logger.error("Recoverable hydration error", {
          error: error instanceof Error ? error.message : String(error),
        });
      }),
    });
  } else {
    createRoot(rootElement).render(tree);
  }
}
