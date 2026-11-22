import { StrictMode } from "react";
import { createRoot, hydrateRoot } from "react-dom/client";
import * as Sentry from "@sentry/react";
import App from "./App.tsx";
import { scrubBreadcrumb, scrubEvent } from "@/lib/sentry";
import { ThemeProvider } from "@/components/ThemeProvider";
import { RevealOnCommit } from "@/components/RevealOnCommit";
import i18n, { toSupportedLanguage } from "@/i18n";
import { setHydrating, shouldHydrate } from "@/lib/hydration";
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/playfair-display/400.css";
import "@fontsource/playfair-display/500.css";
import "@fontsource/playfair-display/600.css";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/500.css";
import "@fontsource/jetbrains-mono/700.css";
import "./index.css";

if (import.meta.env.VITE_SENTRY_DSN) {
  Sentry.init({
    dsn: import.meta.env.VITE_SENTRY_DSN,
    environment: import.meta.env.VITE_APP_ENV ?? (import.meta.env.DEV ? "development" : "production"),
    tracesSampleRate: 0.1,
    // The reset link carries a redeemable token in the query string, and it would
    // otherwise reach the tracker through the event URL and the navigation crumbs.
    beforeSend: scrubEvent,
    beforeBreadcrumb: scrubBreadcrumb,
  });
}

const rootElement = document.getElementById("root");
if (!rootElement) throw new Error("Root element not found");

const tree = (
  <StrictMode>
    <RevealOnCommit>
      <ThemeProvider defaultTheme="system" storageKey="become-theme">
        <App />
      </ThemeProvider>
    </RevealOnCommit>
  </StrictMode>
);

if (shouldHydrate(rootElement, toSupportedLanguage(i18n.language))) {
  setHydrating(true);
  hydrateRoot(rootElement, tree, { onRecoverableError: Sentry.reactErrorHandler() });
} else {
  createRoot(rootElement).render(tree);
}
