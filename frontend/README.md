# BeCoMe frontend

React frontend for BeCoMe (Best Compromise Mean), the system that aggregates expert opinions.

## Tech stack

- React 19 + TypeScript
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

## API proxy

The dev server proxies `/api/v1/*` requests to `http://localhost:8000` (FastAPI backend).

Start the backend first:
```bash
cd .. && SECRET_KEY=dev-secret uv run uvicorn api.main:app --reload
```

## Environment variables

`VITE_API_URL` (API base), `VITE_SENTRY_DSN` (browser error tracking, disabled when the
variable is absent), and `VITE_APP_ENV` (the `dev`, `test`, or `prod` tag on Sentry events).

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
