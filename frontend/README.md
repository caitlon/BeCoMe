# BeCoMe Frontend

React frontend for the BeCoMe (Best Compromise Mean) expert opinion aggregation system.

## Tech Stack

- React 18 + TypeScript
- Vite (build tool)
- Tailwind CSS + shadcn/ui
- React Query (data fetching)
- React Router (routing)

## Development

```bash
# Install dependencies
npm install

# Start dev server (port 8080)
npm run dev

# Build for production
npm run build
```

## API Proxy

The dev server proxies `/api/v1/*` requests to `http://localhost:8000` (FastAPI backend).

Make sure the backend is running:
```bash
cd .. && SECRET_KEY=dev-secret uv run uvicorn api.main:app --reload
```

## Environment variables

`VITE_API_URL` (API base), `VITE_SENTRY_DSN` (browser error tracking; absent disables it),
and `VITE_APP_ENV` (the `dev`/`test`/`prod` tag on Sentry events).

Every one of them has to be declared as an `ARG`/`ENV` pair in `Dockerfile`, before
`RUN npm run build`. Railway passes service variables to the build as build args, but Docker
only exposes the ones the Dockerfile declares, and Vite inlines `undefined` for anything it
cannot see -- with no error and no warning. That is how `VITE_SENTRY_DSN` stayed set on all
three Railway services while `Sentry.init` was tree-shaken out of every deployed bundle.
Adding a new `VITE_*` variable means editing three places: `Dockerfile`, the Railway service,
and the `ImportMetaEnv` interface in `src/vite-env.d.ts`.

## Docker

Build and run with Docker:
```bash
docker build -t become-frontend .
docker run -p 3000:80 become-frontend
```

To reproduce a deployed build locally, pass the build args explicitly:
```bash
docker build --build-arg VITE_API_URL=https://api.becomify.app/api/v1 --build-arg VITE_APP_ENV=prod -t become-frontend .
```

Or use docker-compose from the project root:
```bash
cd ../docker
SECRET_KEY=$(openssl rand -hex 32) docker compose up --build
```
