# BeCoMe REST API

FastAPI-based REST API for the BeCoMe group decision-making method.

## Quick Start

Start the development server:

```bash
uv run uvicorn api.main:app --reload
```

The API will be available at `http://localhost:8000`. Interactive documentation is at `/docs` (Swagger UI) or `/redoc` (ReDoc).

## Endpoints

### Health Check

```
GET /api/v1/health
```

Returns API status and version.

```bash
curl http://localhost:8000/api/v1/health
```

Response:

```json
{"status": "ok", "version": "0.1.0"}
```

### Calculate Best Compromise

```
POST /api/v1/calculate
```

Accepts expert opinions as fuzzy triangular numbers and returns the best compromise along with intermediate results.

```bash
curl -X POST http://localhost:8000/api/v1/calculate \
    -H "Content-Type: application/json" \
    -d '{
        "experts": [
            {"name": "Expert1", "lower": 5, "peak": 10, "upper": 15},
            {"name": "Expert2", "lower": 8, "peak": 12, "upper": 18},
            {"name": "Expert3", "lower": 6, "peak": 11, "upper": 16}
        ]
    }'
```

Response:

```json
{
    "best_compromise": {"lower": 6.5, "peak": 11.0, "upper": 16.0, "centroid": 11.17},
    "arithmetic_mean": {"lower": 6.33, "peak": 11.0, "upper": 16.33, "centroid": 11.22},
    "median": {"lower": 6.0, "peak": 11.0, "upper": 16.0, "centroid": 11.0},
    "max_error": 0.22,
    "num_experts": 3
}
```

## Request/Response Schemas

### ExpertInput

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Expert name or identifier |
| `lower` | float | Lower bound (pessimistic estimate) |
| `peak` | float | Peak value (most likely) |
| `upper` | float | Upper bound (optimistic estimate) |

Constraint: `lower <= peak <= upper`

### CalculateResponse

| Field | Type | Description |
|-------|------|-------------|
| `best_compromise` | FuzzyNumberOutput | Average of arithmetic mean and median |
| `arithmetic_mean` | FuzzyNumberOutput | Component-wise average of all opinions |
| `median` | FuzzyNumberOutput | Middle opinion after sorting by centroid |
| `max_error` | float | Half-distance between mean and median centroids |
| `num_experts` | int | Number of experts in calculation |

### FuzzyNumberOutput

| Field | Type | Description |
|-------|------|-------------|
| `lower` | float | Lower bound |
| `peak` | float | Peak value |
| `upper` | float | Upper bound |
| `centroid` | float | (lower + peak + upper) / 3 |

## Error Handling

| Status Code | Description |
|-------------|-------------|
| 200 | Success |
| 400 | BeCoMe calculation error (invalid input for calculator) |
| 422 | Validation error (malformed request) |
| 500 | Internal server error |

## Module Structure

```
api/
├── __init__.py          # Package marker
├── config.py            # Settings (Pydantic Settings)
├── main.py              # FastAPI app, endpoints, schemas
└── README.md            # This file
```

### config.py

`Settings` class loads configuration from environment variables. Supports `.env` file.

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `false` | Enable debug mode |
| `API_VERSION` | `0.1.0` | API version string |

### main.py

Contains the FastAPI application factory `create_app()`, request/response Pydantic models, and endpoint handlers. The `/calculate` endpoint converts API input to domain models, runs `BeCoMeCalculator`, and returns the result.

## Dependencies

The `api` extra in `pyproject.toml` includes:

- `fastapi` — web framework
- `uvicorn` — ASGI server
- `pydantic-settings` — configuration management
- `httpx` — test client

Install with:

```bash
uv sync --extra api
```

## Testing

API tests are in `tests/api/`. They use FastAPI's `TestClient` and verify results against reference case studies.

```bash
uv run pytest tests/api/ -v
```

## Related Documentation

- [Main README](../README.md) — project overview
- [Source code](../src/README.md) — core library documentation
- [Examples](../examples/README.md) — case studies
