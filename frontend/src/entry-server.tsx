import { StrictMode, type ReactNode } from "react";
import { prerender } from "react-dom/static";
import { StaticRouter } from "react-router";
import i18n from "@/i18n";
import { AppWithRouter } from "@/App";
import { ThemeProvider } from "@/components/ThemeProvider";

/**
 * Renders one route to static HTML, the same tree main.tsx mounts with a static
 * router in place of the browser one.
 *
 * The result is the page a signed-out visitor gets in English and the default
 * theme. No effect runs on the server, so the session probe never starts and
 * the auth context stays in its loading state.
 *
 * @param url - The path to render, for example "/about".
 * @returns The HTML of the app, to go inside the root element.
 */
export async function render(url: string): Promise<string> {
  // Node's navigator.language follows the LANG of the build machine, so the
  // language detector may have picked something other than English.
  await i18n.changeLanguage("en");

  const Router = ({ children }: { children: ReactNode }) => (
    <StaticRouter location={url}>{children}</StaticRouter>
  );
  const { prelude } = await prerender(
    <StrictMode>
      <ThemeProvider defaultTheme="system" storageKey="become-theme">
        <AppWithRouter Router={Router} />
      </ThemeProvider>
    </StrictMode>,
  );
  return new Response(prelude).text();
}
