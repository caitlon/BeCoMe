// Renders the public routes with src/entry-server.tsx in a plain Node process, the way the
// build will, and prints one JSON object of route -> HTML on stdout. The hydration tests run
// in a DOM environment, where a server render would not be a server render: this keeps the
// HTML honest (no window, no document, Node's own globals).
//
// VITE_ASSISTANT_ENABLED in the environment selects the build flavour, as it does for
// `vite build`.
import { createServer } from "vite";

const server = await createServer({
  server: { middlewareMode: true, hmr: false, ws: false },
  appType: "custom",
  logLevel: "error",
});

try {
  const { render } = await server.ssrLoadModule("/src/entry-server.tsx");
  const { publicRoutes } = await server.ssrLoadModule("/src/seo/publicRoutes.ts");
  const pages = {};
  for (const url of [...publicRoutes, "/not-a-page"]) {
    pages[url] = await render(url);
  }
  process.stdout.write(JSON.stringify(pages));
} finally {
  await server.close();
}
