// Writes the prerendered pages into dist/, after `vite build` (the client) and
// `vite build --ssr src/entry-server.tsx --outDir dist-ssr` (the renderer) have run.
//
// dist/index.html, the client build's page, is the template. For every public route this
// script renders the route to HTML, puts it inside <div id="root"> and sets the page's own
// title, description and canonical address in the head. The routes behind a login are not
// prerendered: dist/spa.html, the template with a noindex tag and an empty root, is what
// nginx serves for them. dist/404.html is the not-found page, with a noindex tag and no
// canonical link, which nginx serves with status 404 for every other address.
//
// The root of a public page carries data-route, the route the HTML was rendered for. The
// browser hydrates the page only when that is the route it is on (src/lib/hydration.ts),
// and the 404 page has none, so it is always replaced by a fresh render.
//
// Any problem fails the build: a render error, an empty root, or a script inside the
// rendered HTML.
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

const frontendDir = path.resolve(import.meta.dirname, "..");
const distDir = path.join(frontendDir, "dist");
const entryServer = path.join(frontendDir, "dist-ssr", "entry-server.js");
const origin = "https://www.becomify.app";

function fail(message) {
  console.error(`prerender: ${message}`);
  process.exit(1);
}

function escapeHtml(text) {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

// Replaces the one tag a pattern matches. A template that lost the tag fails the build, so a
// page cannot ship with the template's text in place of its own.
function replaceTag(html, pattern, replacement, label) {
  if (!pattern.test(html)) fail(`the template has no ${label}`);
  return html.replace(pattern, () => replacement);
}

function setMeta(html, attribute, name, content) {
  return replaceTag(
    html,
    new RegExp(`<meta ${attribute}="${name}" content="[^"]*"\\s*/?>`),
    `<meta ${attribute}="${name}" content="${escapeHtml(content)}" />`,
    `<meta ${attribute}="${name}"> tag`,
  );
}

function addToHead(html, tags) {
  const closing = /^([ \t]*)<\/head>/m;
  if (!closing.test(html)) fail("the template has no </head> on a line of its own");
  return html.replace(closing, (_match, indent) => `${tags.map((tag) => `${indent}  ${tag}\n`).join("")}${indent}</head>`);
}

// The template with the rendered HTML inside the root and the page's own title and description.
function fillTemplate(template, rootAttributes, html, meta) {
  const rootTag = '<div id="root"></div>';
  if (!template.includes(rootTag)) fail(`the template has no ${rootTag}`);

  let page = template.replace(rootTag, () => `<div id="root"${rootAttributes}>${html}</div>`);
  page = replaceTag(page, /<title>[^<]*<\/title>/, `<title>${escapeHtml(meta.title)}</title>`, "<title>");
  page = setMeta(page, "name", "description", meta.description);
  page = setMeta(page, "property", "og:title", meta.title);
  page = setMeta(page, "property", "og:description", meta.description);
  page = setMeta(page, "name", "twitter:title", meta.title);
  page = setMeta(page, "name", "twitter:description", meta.description);
  return page;
}

function renderPage(template, route, html, meta) {
  const canonical = `${origin}${route}`;
  return addToHead(fillTemplate(template, ` data-route="${escapeHtml(route)}"`, html, meta), [
    `<link rel="canonical" href="${escapeHtml(canonical)}" />`,
    `<meta property="og:url" content="${escapeHtml(canonical)}" />`,
  ]);
}

function renderNotFoundPage(template, html, meta) {
  return addToHead(fillTemplate(template, "", html, meta), ['<meta name="robots" content="noindex" />']);
}

// Renders one route, failing the build on an error, an empty root or a script in the HTML.
async function renderChecked(url) {
  let html;
  try {
    html = await render(url);
  } catch (error) {
    // render() names the route in its own message.
    fail(error instanceof Error ? error.message : `rendering ${url} failed: ${error}`);
  }
  if (html.trim() === "") fail(`rendering ${url} gave an empty root`);
  if (/<script/i.test(html)) fail(`the HTML of ${url} contains a <script>, which the Content-Security-Policy would block`);
  return html;
}

async function writePage(route, page) {
  const target = route === "/" ? path.join(distDir, "index.html") : path.join(distDir, route, "index.html");
  await mkdir(path.dirname(target), { recursive: true });
  await writeFile(target, page);
  return path.relative(frontendDir, target);
}

let template;
try {
  template = await readFile(path.join(distDir, "index.html"), "utf8");
} catch {
  fail("dist/index.html does not exist: run `vite build` first");
}

let entry;
try {
  entry = await import(pathToFileURL(entryServer).href);
} catch (error) {
  fail(`cannot load dist-ssr/entry-server.js (run the SSR build first): ${error}`);
}
const { render, pageMeta, publicRoutes, notFoundPath, notFoundMeta } = entry;

const written = [];

const spa = addToHead(template, ['<meta name="robots" content="noindex" />']);
const spaTarget = path.join(distDir, "spa.html");
await writeFile(spaTarget, spa);
written.push(path.relative(frontendDir, spaTarget));

// One route after another: render() shares an i18n instance and a query client between calls.
for (const route of publicRoutes) {
  const html = await renderChecked(route);
  written.push(await writePage(route, renderPage(template, route, html, pageMeta(route))));
}

const notFoundTarget = path.join(distDir, "404.html");
await writeFile(notFoundTarget, renderNotFoundPage(template, await renderChecked(notFoundPath), notFoundMeta()));
written.push(path.relative(frontendDir, notFoundTarget));

console.log(`prerender: wrote ${written.length} files`);
for (const file of written) console.log(`  ${file}`);
