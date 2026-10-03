# Contributing to BeCoMe

Thank you for taking an interest in BeCoMe. This page covers how to run the project, how
changes reach the codebase, and where to report problems. The code is under the
[PolyForm Noncommercial 1.0.0](LICENSE) licence.

## Set up and run locally

You need Python 3.13 or higher, [uv](https://docs.astral.sh/uv/) and Node 22. The full
walkthrough, with the dependency groups and the project layout, is in the
[development setup](https://docs.becomify.app/development/).

```bash
uv sync --extra dev --extra api --extra assistant
uv run pre-commit install                  # secret-scanning git hook
cp env/.env.example .env                   # SECRET_KEY has no default
uv run python -m examples.analyze_budget_case
uv run pytest                              # backend tests
```

To run the web application, start the local database, apply the migrations, then start the
API and the frontend. The commands are under "Run it locally" in the development setup.
After `npm install` in `frontend/`, `./scripts/ci/ci-local.sh fast` runs the lint and test
steps that CI runs, without Docker.

## Branches and pull requests

Work moves through three long-lived branches: `dev`, then `test`, then `prod`. Feature and
fix branches are named `<type>/<short-topic>`, for example `docs/contributing-guide`, and
land in `dev` through a pull request, from a fork if you are not a collaborator. Test-only
branches use `tests/<topic>`, because git cannot hold a `test` branch and `test/...` branches
together. Nothing is committed to the three long-lived branches directly, and the promotion
pull requests between them are opened by the maintainer.

- Fill in the five sections of the [pull request template](.github/pull_request_template.md).
- Keep a pull request small and about one thing. The target is 300 to 600 changed lines.
  A size label (`size:S` to `size:XL`) is applied automatically, and anything over 1000
  lines should be split.
- Write commit messages and titles as `<type>: <short description>`, with the types `feat`,
  `fix`, `refactor`, `test`, `docs`, `chore`, `ci` and `style`.
- CI runs linting, type checking, secret scanning, the docs build, a dependency audit and
  the backend, frontend and end-to-end tests, and fails the backend run below 98 percent
  coverage. The `Check` job collects all of them and must be green before a pull request is
  merged.

## Reporting problems

Open an issue with one of the [issue forms](https://github.com/caitlon/BeCoMe/issues/new/choose)
for a bug, a feature request or technical debt. Do not post secrets or personal data in a
public issue.

Report security problems privately, following the [security policy](.github/SECURITY.md),
and never in a public issue.

## Documentation

The documentation site is [docs.becomify.app](https://docs.becomify.app). Its sources are
under [docs/](docs), and each part of the code has a README next to it:
[src/](src/README.md), [api/](api/README.md), [frontend/](frontend/README.md) and
[tests/](tests/README.md). The method itself is described in the
[method description](https://docs.becomify.app/method-description/).
