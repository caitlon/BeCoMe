# BeCoMe frontend

React frontend for BeCoMe (Best Compromise Mean), the system that aggregates expert opinions.

## Contents

- [Tech stack](#tech-stack)
- [Development](#development)
- [API proxy](#api-proxy)
- [Environment variables](#environment-variables)
- [Docker](#docker)
- [Internationalisation](#internationalisation)
- [Accessibility](#accessibility)
- [Layout](#layout)
- [Assistant](#assistant)
- [Server rendering](#server-rendering)
- [Testing](#testing)

## Tech stack

- React 19 + TypeScript
- Vite (build tool)
- Tailwind CSS + shadcn/ui
- Radix UI primitives, wrapped as the shadcn/ui components in `src/components/ui`
- React Query (data fetching)
- React Hook Form with Zod (forms and schema validation)
- Recharts (charts)
- Framer Motion (animation)
- React Router (routing)
- i18next with react-i18next (English and Czech)
- Sentry (`@sentry/react`, browser error tracking)
- react-markdown (assistant answers, rendered from an allowlist of elements)
- Cloudflare Turnstile (bot check on the sign-in, registration, password reset and resend-verification forms)
- Vitest with Testing Library (unit tests)
- Playwright with axe-core (end-to-end and accessibility tests)

## Development

Run these from `frontend/`.

```bash
# Install dependencies
npm install

# Start dev server (port 8080)
npm run dev

# Build for production
npm run build

# Lint and type check
npm run lint
npm run typecheck

# Unit tests: watch mode, one run, one run with the coverage gate
npm test
npm run test:run
npm run test:coverage

# End-to-end tests (see Testing before a bare run)
npm run test:e2e
```

## API proxy

The dev server proxies `/api/v1/*` requests to `http://localhost:8000` (FastAPI backend).

Start the backend first:
```bash
cd .. && SECRET_KEY=dev-secret uv run uvicorn api.main:app --reload
```

## Environment variables

- `VITE_API_URL`: base URL of the API. Falls back to `/api/v1` when unset, which the dev
  server proxies. The Dockerfile also copies its origin into the Content-Security-Policy.
- `VITE_SENTRY_DSN`: DSN for browser error tracking. Tracking stays off when it is absent.
- `VITE_APP_ENV`: the `dev` or `prod` tag on Sentry events.
- `VITE_TURNSTILE_SITE_KEY`: Cloudflare Turnstile site key. When it is empty, the forms draw
  no widget and submit without a token.
- `VITE_ASSISTANT_ENABLED`: build flag for the assistant panel. Only the exact string `true`
  includes it in the bundle; prod leaves it unset. See the Assistant section.

Declare every one of them as both an `ARG` and an `ENV` in `Dockerfile`, before
`RUN npm run build`. Railway passes service variables to the build as build args, but Docker
only exposes the ones the Dockerfile declares, and Vite inlines `undefined` for anything it
cannot see, with no error and no warning. That is how `VITE_SENTRY_DSN` stayed set on all
three Railway services while the bundler tree-shook `Sentry.init` out of every deployed bundle.
A new `VITE_*` variable means editing three places: `Dockerfile`, the Railway service, and the
`ImportMetaEnv` interface in `src/vite-env.d.ts`.

`CLOUDFLARE_ORIGIN_SECRET` is not a `VITE_*` variable: the container reads it at start, so it
is no build arg and needs no `Dockerfile` or `vite-env.d.ts` entry. On Railway it is a reference
to the same variable of the backend service, and outside Railway the origin check is off when it
is unset (`docker-entrypoint.d/40-origin-lock.sh`, rotation in `docs/secrets.md`).

`GET /healthz` answers 200 with an empty body, as the health path for Railway's check on dev and
prod. Like `/`, it needs no secret when the request is addressed to `healthcheck.railway.app`.

## Docker

Build and run with Docker:
```bash
docker build -t become-frontend .
docker run -p 3000:8080 become-frontend
```

To reproduce a deployed build locally, pass the build args explicitly:
```bash
docker build --build-arg VITE_API_URL=https://api.becomify.app/api/v1 --build-arg VITE_APP_ENV=prod -t become-frontend .
```

Or use Docker Compose from the `docker/` directory:
```bash
cd ../docker
SECRET_KEY=$(openssl rand -hex 32) docker compose up --build
```

The stack serves the app on http://localhost:3000 and the API on http://localhost:8000. Sign in with Chrome or Firefox: the session cookies are always Secure, and Safari does not store a Secure cookie set over plain HTTP on localhost.

## Internationalisation

The interface is in English (`en`) and Czech (`cs`). The strings live in
`src/i18n/locales/en/` and `src/i18n/locales/cs/`, one JSON file per namespace, with
`common` as the default. A new namespace has to be imported and registered in
`src/i18n/index.ts`.

Both locales must carry the same keys. `tests/i18n/key-parity.test.ts` compares the key set of
every namespace, and the set of namespaces itself.

A string that depends on a count uses i18next plural suffixes: `key_one`, `key_other` and so on,
called with `t("key", { count })`. English carries `_one` and `_other`, Czech `_one`, `_few`,
`_many` and `_other`, which are the categories `Intl.PluralRules` reports for each language. The
parity test folds the suffixes into one key before it compares the locales, and checks that every
group has exactly the categories of its language.

The language is taken from `localStorage` under the key `become-language`, then from the
browser's language list, and falls back to English. A choice made with the language switcher
is stored under the same key. Only `en` and `cs` are supported, and a regional tag such as
`cs-CZ` resolves to Czech. The `lang` attribute of `<html>` follows the interface language.

The three calls that send a localised email, `register`, `resendVerification` and
`forgotPassword`, pass the interface language in the `Accept-Language` header.
`languageHeaders()` in `src/lib/api.ts` builds it and `get_email_language` in
`api/dependencies.py` reads it.

## Accessibility

- **Skip link.** It is defined in `index.html`, outside the React root, so it exists before
  React mounts and is the first Tab stop. `.skip-to-content` in `src/index.css` keeps it off
  screen until it has focus. Its text comes from the `a11y.skipToContent` key and is updated
  when the language changes (`src/i18n/index.ts`).
- **Route changes.** On a change of pathname, `RouteAnnouncer` scrolls to the top, moves focus
  to `#main-content`, and announces `document.title` in a polite live region. It does nothing
  on the first load, so the skip link stays the first Tab stop.
- **Loading placeholder.** While a page or the session check loads, `PageLoader` is the skip
  link's target and, if it held focus when the page replaces it, hands focus to that page's `main`.
- **Page titles.** `useDocumentTitle` sets the title to `<page> - BeCoMe`; the home page passes
  `suffix: false` and is titled "BeCoMe - Best Compromise Mean". Every component in `src/pages`
  calls it.
- **Control names.** The close buttons of dialogs and toasts and the toast region take their
  names from the `a11y.close` and `a11y.notifications` keys (`src/components/ui/dialog.tsx`,
  `src/components/ui/toast.tsx`). The language switcher's accessible name comes from the
  `switchToLanguage` key, for example "EN, switch to Čeština".
- **Audit.** `e2e/wcag-audit.spec.ts` runs axe-core with the WCAG 2.0 and 2.1 A and AA tags. It
  covers the landing, about, docs, FAQ, privacy, terms, case studies, case study, login, register and
  404 pages, the landing and login pages in the dark theme, and the projects, onboarding and
  profile pages of a signed-in user.

## Layout

The navigation bar shows its full row from the `xl` breakpoint (1280 px) and a menu button
below it, and a long signed-in name is truncated.

## Assistant

The assistant panel is behind the build flag `VITE_ASSISTANT_ENABLED`. It is off by default,
and a default build carries no assistant code, strings, i18n keys or endpoint paths. CI checks this
with `scripts/ci/check-assistant-bundle.sh` on a build without the flag and a build with it. The
panel, its triggers, the privacy card on the profile page, the documentation section and the
onboarding tour step are lazy chunks that exist only when the flag is set.
Build with the flag to include it:
```bash
VITE_ASSISTANT_ENABLED=true npm run build
```

The feature lives in `src/components/assistant/`. Its backend half needs `ASSISTANT_ENABLED`
on the API and runs on a developer machine and on the dev and prod services (`api/assistant/README.md`).

`e2e/assistant-panel.spec.ts` needs no backend: it answers every API request with a route.
It is skipped unless the flag is in the environment when Playwright starts its dev server:
```bash
VITE_ASSISTANT_ENABLED=true npx playwright test e2e/assistant-panel.spec.ts --project=chromium
```

## Server rendering

`npm run build` renders the public pages to HTML at build time, and the browser hydrates them.
It runs three steps: `vite build` (the client), `vite build --ssr src/entry-server.tsx --outDir dist-ssr`
(the renderer, never shipped: the Dockerfile copies `dist/` only) and `node scripts/prerender.mjs`.

- `src/entry-server.tsx` exports `render(url)`, which returns the HTML of one route as a signed-out
  visitor sees it in English and the default theme. It rejects when React reports any error, a
  failure inside a Suspense boundary included, so a broken page fails the build instead of shipping
  its loader. `pageMeta(path)` returns the title and description of a public route, built from the
  same i18n keys and the same `documentTitle()` rule the page uses at runtime. `App.tsx` exports
  `AppWithRouter`, the same tree with the router passed in, so the server can use a static one.
- `src/seo/publicRoutes.ts` lists the routes that need no login, with the keys of their title and
  description. A route added there gets a prerendered page, and `tests/seo/page-titles.test.tsx`
  fails when its title differs from the one the page sets in a browser. The 404 page gets the same
  check through `notFoundMeta()`, but it is not in `publicRoutes`, which would list it for indexing.
- `scripts/prerender.mjs` takes the built `dist/index.html` as the template and renders the routes one
  after another, because `render` shares an i18n instance and a query client between calls. Each page
  gets its HTML inside `#root` and its own `<title>`, description, `og:` and `twitter:` text, a
  canonical link and `og:url` on `https://www.becomify.app`. Its root is
  `<div id="root" data-route="/about">`, the route the HTML was rendered for. It writes
  `dist/index.html` for `/` and `dist/<path>/index.html` for the rest. It fails the build on an empty
  root, a `<script>` in the rendered HTML or a render error. It also writes two pages that are not
  routes and are not indexed. `dist/spa.html` is the template with
  `<meta name="robots" content="noindex" />` and an empty root, the page nginx serves for the routes
  behind a login. `dist/404.html` is the not-found page (`render(notFoundPath)`), with its own title,
  the noindex tag, no canonical link and no `data-route`.
- `nginx.conf` serves a request from `dist/` as `$uri`, then `$uri/index.html`, and answers 404
  otherwise, with `404.html` as the body, so a crawler never meets a soft 404. A short allowlist of
  the routes behind a login (`/login`, `/register`, `/forgot-password`, `/reset-password`,
  `/verify-email`, `/projects`, `/projects/<id>`, `/profile`, `/onboarding`, with or without a
  trailing slash) gets `spa.html` with status 200. The asset location comes first and wins for any
  path with an asset extension, so a missing `/assets/x.js` is a 404. The HTML sends
  `Cache-Control: no-cache`, except the 404 page, where `expires` does nothing. Trying the directory
  itself (`$uri/`) would answer `/about` with a redirect to the container's port 8080. The 404
  page and the app routes set no `add_header` of their own, so they get the server-level security
  headers; the asset location repeats them, because a location with its own `add_header` stops
  inheriting.
- `tests/seo/routes-in-nginx.test.ts` reads the `<Route path>` values from `src/App.tsx` and the
  allowlist from `nginx.conf`. Each route must be either in `publicRoutes` or in the allowlist, never
  both, and neither list may hold a path `App.tsx` lacks. A route added to `App.tsx` alone fails
  there instead of shipping as a 404. The allowlist is case-sensitive, so `/Login` is a 404 for nginx,
  but the browser mounts fresh over the 404 page and the router, which ignores case, shows the page.
- `src/lib/mount.ts`, called from `src/main.tsx`, hydrates when `#root` has prerendered content, the
  detected language is English and `data-route` equals the current path (a trailing slash ignored),
  and mounts a fresh tree otherwise. The 404 page is served at any unknown address, such as
  `/case-study/unknown`, which the router renders differently, so it has no `data-route` and always
  mounts fresh. A Czech visitor gets a fresh render, and the pre-paint script
  keeps `#root` hidden until `RevealOnCommit` clears `lang-pending` after the first commit.
- `src/lib/hydration.ts` holds a flag `mountApp` sets right before `hydrateRoot` and never
  clears: it says this page load started from server HTML. While it is set, the first render must
  match the server's HTML: `ThemeProvider` starts from its default theme
  and applies the stored one afterwards, inside `startTransition`. Updates that can arrive while a lazy
  page is still hydrating, such as the session probe in `AuthContext`, are transitions too, because a
  plain update makes React discard the server HTML of that page. The copyright year in the footer is
  the one text allowed to differ (`suppressHydrationWarning`).
- A small inline script in `index.html` runs before first paint. It adds the stored (or system) theme
  class to `<html>` and, for Czech visitors, a `lang-pending` class that `index.css` uses to hide `#root`
  until React has committed its first render (`RevealOnCommit` removes it; a CSS animation reveals the
  page after three seconds if the bundle never loads). `nginx.conf` allows the script by its sha256
  hash, so editing the script means updating the hash there; `tests/integration/test_frontend_csp.py`
  checks it.

`scripts/ci/check-prerender.sh` checks a build: every public route has its file with a non-empty root
that names its route, its title, its description and its canonical link, `spa.html` has the noindex tag
and an empty root, `404.html` has its title, the noindex tag, no canonical link and no `data-route`, and
every inline script of every built page has its hash in the Content-Security-Policy. With `--docker` it
also builds the image, runs it and fetches `/`, `/about`, `/about/`, a case study and every app route
of the nginx allowlist (`/projects/123` for the project page, `/profile/` for the trailing slash),
expecting status 200 with no redirect, the security headers, `no-cache` and the right page (the shell
for the app routes). It then fetches `/no-such-page` and `/case-study/unknown`, expecting status 404
with the not-found page and the security headers, and `/assets/missing.js` and `/projects/x.js`,
expecting 404 with the security headers and no app shell. The list of app routes it fetches is written
out in the script, so a route added to the allowlist has to be added there too. CI runs both after
the frontend build.

## Testing

Unit tests live in `tests/` and run under Vitest with happy-dom. The subdirectories are
`components`, `contexts`, `data`, `hooks`, `i18n`, `lib`, `pages`, `seo` and `ssr`, plus `factories`,
`mocks` and `support` for shared test data, API mocks and the hydration helpers.

`tests/ssr/entry-server.test.tsx` runs the server render in the node environment, with no DOM. The
hydration tests (`hydration.test.tsx`, and `hydration.reduced-motion.test.tsx` in a file of its own
because framer-motion reads that preference once per process) get their HTML from a separate Node
process, `tests/support/render-server-html.mjs`, which loads `src/entry-server.tsx` through Vite's SSR
loader. They put that HTML in the page, run `hydrateRoot` over it, and expect no recoverable error, no
console error and the server's own nodes still attached, for every public route in several browser
states and with the assistant flag on and off.

`npm run test:coverage` fails below these thresholds (`vitest.config.ts`): statements 98,
branches 95, functions 97, lines 98. `./scripts/ci/ci-local.sh fast` runs `npm run test:run`
and does not check them, while CI runs `npm run test:coverage`. Run the coverage command
before pushing a frontend change.

Playwright specs live in `e2e/`. The dev server for them runs over HTTPS, because the session
cookies carry the `__Host-` prefix. The specs register real users, so they need the API and a
database. `./scripts/ci/e2e-local.sh` starts PostgreSQL in Docker and the API, then runs them.
The projects in `playwright.config.ts`:

- `chromium`, `firefox`, `webkit`: the functional specs.
- `wcag-audit`: the axe audit above.
- `visual-regression`: page screenshots of the landing hero, a case study and the
  project results charts, each in the light and dark theme, plus one 430 px light-theme
  shot of the results card (the triangle legend on a narrow screen).
- `docs-screenshots`: illustrations for the documentation site, not a check. It overwrites
  the tracked images in `docs/user/img/`, so name the project with `--project=` and do not
  rely on a bare `npm run test:e2e`.

The visual baselines live in `e2e/visual-regression.spec.ts-snapshots/`. The committed ones are
Linux renders (`*-linux.png`), and git ignores `*-darwin.png` (`frontend/.gitignore`). A render from a
Mac does not match what CI compares against, so do not regenerate them locally. After an
intended layout change, take the new images from the Playwright report of the failed CI run
instead. The header of `.github/workflows/regen-snapshots.yml` lists the steps.
