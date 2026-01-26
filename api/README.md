# BeCoMe REST API

FastAPI-based REST API for the BeCoMe group decision-making method.

## Quick Start

```bash
uv sync --extra api
uv run uvicorn api.main:app --reload
```

The API runs at `http://localhost:8000`. Interactive documentation:
- Swagger UI: `/docs`
- ReDoc: `/redoc`

## Module Structure

```
api/
├── auth/               # Authentication & authorization
│   ├── jwt.py              # Token creation/validation
│   ├── password.py         # Password hashing (bcrypt)
│   ├── dependencies.py     # CurrentUser dependency
│   ├── token_blacklist.py  # Revoked tokens storage
│   └── logging.py          # Auth event logging
├── db/                 # Database layer
│   ├── models.py           # SQLModel entities
│   ├── engine.py           # Database engine setup
│   ├── session.py          # Session dependency
│   └── utils.py            # UTC helpers, email regex
├── middleware/         # Request processing
│   ├── rate_limit.py       # SlowAPI rate limiting
│   ├── security_headers.py # Security response headers
│   └── exception_handlers.py
├── routes/             # HTTP endpoints
│   ├── auth.py             # /api/v1/auth/*
│   ├── users.py            # /api/v1/users/*
│   ├── projects.py         # /api/v1/projects/*
│   ├── opinions.py         # /api/v1/projects/{id}/opinions
│   ├── invitations.py      # /api/v1/invitations/*
│   ├── calculate.py        # /api/v1/calculate
│   └── health.py           # /api/v1/health
├── schemas/            # Pydantic DTOs
│   ├── auth.py             # Login, register, tokens
│   ├── project.py          # Project CRUD
│   ├── opinion.py          # Expert opinions
│   ├── invitation.py       # Project invitations
│   ├── calculation.py      # BeCoMe calculation I/O
│   └── ...
├── services/           # Business logic
│   ├── user_service.py
│   ├── project_service.py
│   ├── opinion_service.py
│   ├── invitation_service.py
│   ├── calculation_service.py
│   └── storage/            # File storage (Supabase)
├── utils/              # Utilities
│   └── sanitization.py     # HTML sanitization
├── config.py           # Settings (Pydantic Settings)
├── dependencies.py     # DI factories + authorization
├── exceptions.py       # API exception hierarchy
└── main.py             # FastAPI application
```

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Register new user |
| POST | `/api/v1/auth/login` | Login, get tokens |
| POST | `/api/v1/auth/logout` | Revoke refresh token |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| GET | `/api/v1/auth/me` | Get current user profile |

### Users

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/users/me` | Get profile |
| PUT | `/api/v1/users/me` | Update profile |
| PUT | `/api/v1/users/me/password` | Change password |
| POST | `/api/v1/users/me/photo` | Upload photo |
| DELETE | `/api/v1/users/me/photo` | Delete photo |
| DELETE | `/api/v1/users/me` | Delete account |

### Projects

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/projects` | List user's projects |
| POST | `/api/v1/projects` | Create project |
| GET | `/api/v1/projects/{id}` | Get project details |
| PATCH | `/api/v1/projects/{id}` | Update project |
| DELETE | `/api/v1/projects/{id}` | Delete project |
| GET | `/api/v1/projects/{id}/members` | List members |
| DELETE | `/api/v1/projects/{id}/members/{user_id}` | Remove member |
| POST | `/api/v1/projects/{id}/invite` | Invite user |

### Opinions

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/projects/{id}/opinions` | List opinions |
| POST | `/api/v1/projects/{id}/opinions` | Submit opinion |
| DELETE | `/api/v1/projects/{id}/opinions` | Delete own opinion |

### Invitations

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/invitations` | List pending invitations |
| POST | `/api/v1/invitations/{id}/accept` | Accept invitation |
| POST | `/api/v1/invitations/{id}/decline` | Decline invitation |

### Calculation

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/calculate` | Calculate BeCoMe (standalone) |
| GET | `/api/v1/projects/{id}/result` | Get project calculation result |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | API health check |

## Configuration

Environment variables (can use `.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./become.db` | Database connection string |
| `SECRET_KEY` | *required* | JWT signing key |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Access token TTL |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token TTL |
| `DEBUG` | `false` | Debug mode |
| `API_VERSION` | `0.1.0` | API version |
| `CORS_ORIGINS` | `localhost:3000,8080` | Allowed CORS origins |
| `SUPABASE_URL` | *optional* | Supabase project URL |
| `SUPABASE_KEY` | *optional* | Supabase service key |

## Testing

```bash
# Run all API tests
uv run pytest tests/api/ -v

# Run with coverage
uv run pytest tests/api/ --cov=api --cov-report=term-missing
```

## Related Documentation

- [Main README](../README.md) — project overview
- [CLAUDE.md](../CLAUDE.md) — development guidelines
