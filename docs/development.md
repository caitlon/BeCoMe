# Development setup

Everything needed to run BeCoMe locally: the toolchain, the dependency groups, and where
each part of the tree lives. For what the method does, read the [method
description](method-description.md). For the deployed profiles, read
[environments](environments.md).

## Contents

- [Requirements](#requirements)
- [Install](#install)
- [Dependency groups](#dependency-groups)
- [Configuration](#configuration)
- [Build the documentation site](#build-the-documentation-site)
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
# or, on Windows:
.venv\Scripts\activate
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
| `docs` | mkdocs, mkdocs-material | Building the documentation site |

## Configuration

Templates for every environment variable live under `env/`. Copy the base to the repository
root before the first run, because `SECRET_KEY` has no default and the application refuses to
start without it:

```bash
cp env/.env.example .env
```

Profiles, what each one changes, and the per-profile templates are in
[environments](environments.md).

## Build the documentation site

The site is not part of the default install. `mkdocs` lives in the `docs` extra, so it needs
naming explicitly:

```bash
uv run --extra docs mkdocs serve   # live preview on http://localhost:8000
uv run --extra docs mkdocs build --strict   # what CI will run: fails on a broken link
```

`--strict` is the one that matters. Pages under `docs/dev/` are one include line each, pulling
in a README that lives next to the code, so a moved file or a link that only resolves inside
the repository turns into a build failure rather than a broken page.

The long documents carry a generated table of contents, and CI checks it in the same job:

```bash
uv run --extra docs python scripts/docs/toc.py --check   # exit 1 and names what is stale
uv run --extra docs python scripts/docs/toc.py --write   # rewrite them
```

The build already catches a renamed heading, failing on the entry that now points at nothing.
The check covers what it cannot: a heading added with no entry, where nothing breaks and the map
is only incomplete, and the two documents that never reach the site at all.
With no paths it works on every tracked document over 100 lines or over 6 sections, so one that
grows into needing a map gets picked up on its own.

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

The dev profile is the default and needs no profile file of its own, only the base `.env`. Profiles, Railway variables, and
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
