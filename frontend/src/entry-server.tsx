import { StrictMode, type ReactNode } from "react";
import { prerender } from "react-dom/static";
import { StaticRouter } from "react-router";
import i18n from "@/i18n";
import { AppWithRouter } from "@/App";
import { ThemeProvider } from "@/components/ThemeProvider";
import { documentTitle } from "@/hooks/useDocumentTitle";
import { publicRouteMeta } from "@/seo/publicRoutes";

export { publicRoutes } from "@/seo/publicRoutes";

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
 * @throws When React reports any error while rendering, including one inside a
 *   Suspense boundary, which React would otherwise swallow by leaving the
 *   boundary's fallback for the client to replace. A page like that must not ship.
 */
export async function render(url: string): Promise<string> {
  // Node's navigator.language follows the LANG of the build machine, so the
  // language detector may have picked something other than English.
  await i18n.changeLanguage("en");

  const Router = ({ children }: { children: ReactNode }) => (
    <StaticRouter location={url}>{children}</StaticRouter>
  );
  const errors: unknown[] = [];
  const { prelude } = await prerender(
    <StrictMode>
      <ThemeProvider defaultTheme="system" storageKey="become-theme">
        <AppWithRouter Router={Router} />
      </ThemeProvider>
    </StrictMode>,
    {
      onError: (error) => {
        errors.push(error);
      },
    },
  );
  const html = await new Response(prelude).text();
  if (errors.length > 0) {
    const messages = errors.map((error) => (error instanceof Error ? error.message : String(error)));
    throw new Error(`Rendering ${url} failed: ${messages.join("; ")}`);
  }
  return html;
}

interface PageMeta {
  readonly title: string;
  readonly description: string;
}

/**
 * The title and description of one public route, in English: what the page sets
 * as its document title at runtime and what its hero says.
 *
 * @param path - One of the paths in `publicRoutes`.
 * @throws When the path is not a public route.
 */
export function pageMeta(path: string): PageMeta {
  const route = publicRouteMeta.find((candidate) => candidate.path === path);
  if (!route) throw new Error(`No page metadata for ${path}`);
  const t = (key: string, name?: string) => i18n.t(key, { lng: "en", name });
  const name = route.titleNameKey ? t(route.titleNameKey) : undefined;
  return {
    title: documentTitle(t(route.titleKey, name), route.titleSuffix),
    description: t(route.descriptionKey),
  };
}
