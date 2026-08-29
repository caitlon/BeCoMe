# Development setup

Everything needed to run BeCoMe locally: the toolchain, the dependency groups, and where each
part of the tree lives. For what the method does, read the
[method description](method-description.md). For the deployed profiles, read
[environments](environments.md).

## Contents

- [Requirements](#requirements)
- [Install](#install)
- [Dependency groups](#dependency-groups)
- [Run it locally](#run-it-locally)
- [Project structure](#project-structure)

## Requirements

- Python 3.13 or higher
- `uv` for dependency management (or `pip`)
- Node 22 for the frontend

## Install

```bash
git clone <repository-url>
cd BeCoMe

uv sync                    # core library only
uv sync --extra api        # add the REST API
uv sync --extra dev        # add testing, linting, type checking
uv sync --all-extras       # everything

source .venv/bin/activate  # macOS and Linux
.venv\Scripts\activate     # Windows
```

After installing the `dev` extra, enable the local secret-scanning git hook:

```bash
uv run pre-commit install
```

With pip instead:

```bash
pip install -e ".[dev,viz,notebook]"
```

## Dependency groups

| Group | Contents | Use case |
|-------|----------|----------|
| (core) | pydantic | Minimal installation for using the library |
| `api` | fastapi, uvicorn, sqlmodel, alembic, redis, boto3 | Running the REST API |
| `dev` | pytest, hypothesis, mypy, ruff, bandit, detect-secrets, pre-commit | Development, testing, security |
| `viz` | numpy, pandas, matplotlib, plotly, seaborn | Visualization and data analysis |
| `notebook` | jupyter, ipykernel, ipywidgets | Interactive notebooks |

## Run it locally

```bash
# Backend on http://localhost:8000
uv sync --extra api
uv run uvicorn api.main:app --reload

# Frontend on http://localhost:8080
cd frontend && npm install && npm run dev
```

Run one case study without the web app:

```bash
uv run python -m examples.analyze_budget_case
```

The dev profile is the default and needs no configuration. Profiles, Railway variables, and
deployment live in [environments](environments.md).

## Project structure

```text
BeCoMe/
├── api/                    # REST API (FastAPI)
│   ├── auth/                   # Authentication (JWT, passwords, session cookies, throttles)
│   ├── db/                     # Database models (SQLModel)
│   ├── middleware/             # Rate limit, CSRF, body size, security headers, logging
│   ├── routes/                 # HTTP endpoints
│   ├── schemas/                # Pydantic DTOs
│   ├── services/               # Business logic
│   └── README.md               # API documentation
├── frontend/               # Web UI (React + Vite)
│   ├── src/
│   │   ├── components/         # UI components (shadcn/ui)
│   │   ├── pages/              # Route pages
│   │   ├── contexts/           # React contexts
│   │   └── i18n/               # Translations (en, cs)
│   └── README.md
├── src/                    # Core library
│   ├── models/                 # Fuzzy number, expert opinion
│   ├── calculators/            # BeCoMe algorithm
│   └── interpreters/           # Likert scale support
├── tests/                  # Test suite (1,786 backend tests)
│   ├── unit/                   # Unit tests (models, calculators, API)
│   ├── integration/            # Integration tests (Excel validation, API routes, DB)
│   ├── e2e/                    # End-to-end API tests
│   └── reference/              # Expected values from Excel
├── examples/               # Case study examples
│   └── data/                   # Dataset files
└── docs/                   # Documentation
```
