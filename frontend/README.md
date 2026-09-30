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
- `VITE_APP_ENV`: the `dev`, `test`, or `prod` tag on Sentry events.
- `VITE_TURNSTILE_SITE_KEY`: Cloudflare Turnstile site key. When it is empty, the forms draw
  no widget and submit without a token.

Declare every one of them as both an `ARG` and an `ENV` in `Dockerfile`, before
`RUN npm run build`. Railway passes service variables to the build as build args, but Docker
only exposes the ones the Dockerfile declares, and Vite inlines `undefined` for anything it
cannot see, with no error and no warning. That is how `VITE_SENTRY_DSN` stayed set on all
three Railway services while the bundler tree-shook `Sentry.init` out of every deployed bundle.
A new `VITE_*` variable means editing three places: `Dockerfile`, the Railway service, and the
`ImportMetaEnv` interface in `src/vite-env.d.ts`.

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

## Internationalisation

The interface is in English (`en`) and Czech (`cs`). The strings live in
`src/i18n/locales/en/` and `src/i18n/locales/cs/`, one JSON file per namespace, with
`common` as the default. A new namespace has to be imported and registered in
`src/i18n/index.ts`.

Both locales must carry the same keys. `tests/i18n/key-parity.test.ts` compares the key set of
every namespace, and the set of namespaces itself.

The language is taken from `localStorage` under the key `become-language`, then from the
browser's language list, and falls back to English. A choice made with the language switcher
is stored under the same key. Only `en` and `cs` are supported, and a regional tag such as
`cs-CZ` resolves to Czech. The `lang` attribute of `<html>` follows the interface language.

The two calls that send a localised email, `register` and `resendVerification`, pass the
interface language in the `Accept-Language` header. `languageHeaders()` in `src/lib/api.ts`
builds it and `get_email_language` in `api/dependencies.py` reads it. The password-reset email
carries no language.

## Accessibility

- **Skip link.** It is defined in `index.html`, outside the React root, so it exists before
  React mounts and is the first Tab stop. `.skip-to-content` in `src/index.css` keeps it off
  screen until it has focus. Its text comes from the `a11y.skipToContent` key and is updated
  when the language changes (`src/i18n/index.ts`).
- **Route changes.** On a change of pathname, `RouteAnnouncer` scrolls to the top, moves focus
  to `#main-content`, and announces `document.title` in a polite live region. It does nothing
  on the first load, so the skip link stays the first Tab stop.
- **Page titles.** `useDocumentTitle` sets the title to `<page> - BeCoMe`. Every component in
  `src/pages` calls it.
- **Control names.** The close buttons of dialogs and toasts and the toast region take their
  names from the `a11y.close` and `a11y.notifications` keys (`src/components/ui/dialog.tsx`,
  `src/components/ui/toast.tsx`). The language switcher's accessible name comes from the
  `switchToLanguage` key, for example "EN, switch to Čeština".
- **Audit.** `e2e/wcag-audit.spec.ts` runs axe-core with the WCAG 2.0 and 2.1 A and AA tags. It
  covers the landing, about, docs, FAQ, privacy, case studies, case study, login, register and
  404 pages, the landing and login pages in the dark theme, and the projects, onboarding and
  profile pages of a signed-in user.

## Layout

The navigation bar shows its full row from the `xl` breakpoint (1280 px) and a menu button
below it, and a long signed-in name is truncated.

## Testing

Unit tests live in `tests/` and run under Vitest with happy-dom. The subdirectories are
`components`, `contexts`, `data`, `hooks`, `i18n`, `lib` and `pages`, plus `factories` and
`mocks` for shared test data and API mocks.

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
  project results charts, each in the light and dark theme.
- `docs-screenshots`: illustrations for the documentation site, not a check. It overwrites
  the tracked images in `docs/user/img/`, so name the project with `--project=` and do not
  rely on a bare `npm run test:e2e`.

The visual baselines live in `e2e/visual-regression.spec.ts-snapshots/`. The committed ones are
Linux renders (`*-linux.png`), and git ignores `*-darwin.png` (`frontend/.gitignore`). A render from a
Mac does not match what CI compares against, so do not regenerate them locally. After an
intended layout change, take the new images from the Playwright report of the failed CI run
instead. The header of `.github/workflows/regen-snapshots.yml` lists the steps.
