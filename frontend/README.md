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

## Docker

Build and run with Docker:
```bash
docker build -t become-frontend .
docker run -p 3000:80 become-frontend
```

Or use docker-compose from the project root:
```bash
cd ../docker
SECRET_KEY=$(openssl rand -hex 32) docker compose up --build
```
