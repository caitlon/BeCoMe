# Local assistant

Runs only on a developer machine. `Settings` refuses to start any deployed profile with
`ASSISTANT_ENABLED=true`.

## Prerequisites

- `brew install llama.cpp`
- `uv sync --extra dev --extra api --extra assistant`
- Docker, for the vector database

## Start

1. Vector database: `SECRET_KEY=unused docker compose -f docker/docker-compose.yml --profile
   assistant up -d --wait assistant-db`. Compose interpolates the whole file before picking a
   service to start, and the `api` service's own required `SECRET_KEY` variable would otherwise
   fail that step even though `assistant-db` never reads it, so any value satisfies it.
2. In `.env`: `ASSISTANT_VECTOR_DB_URL=postgresql+psycopg://assistant@127.0.0.1:5433/assistant`.
   The URL has no default, and both the indexer and the backend read it; every other
   `ASSISTANT_*` variable is listed in `env/.env.example`.
3. Model servers: `./scripts/assistant/run-llama-servers.sh`
4. Index the documentation: `uv run python scripts/assistant/ingest.py --name docs_default
   --strategy markdown_headers` builds the collection the backend reads by default; `--help`
   lists the chunker, context and wave options.
5. Evaluate retrieval quality: `uv run python scripts/assistant/eval_retrieval.py --collection
   docs_default` scores hit@1/3/5, MRR and nDCG@5 for that collection against the golden set
   (`scripts/assistant/golden_set.jsonl` by default; point `--golden-set` at another file to use
   a different one). Every report also records the collection's `app_version` and
   `corpus_version` from the `assistant_collections` registry, and is written to
   `supplementary/assistant-eval/<collection>-<timestamp>.json`.
6. Backend: set `ASSISTANT_ENABLED=true` in `.env`, then run the API as usual. This turns on
   `GET /api/v1/assistant/config` (`api/routes/assistant.py`), the only assistant route so far.

## Private corpus layer

Articles, thesis chapters and book excerpts are copyrighted, so they never enter this
repository. Keep copies in a separate local git repository with no remote, for example
`supplementary/assistant/corpus/` (this repository ignores the whole `supplementary` folder):
one folder per corpus wave and a `manifest.json` at its root, whose relative paths start from
the manifest's own folder. Point `ASSISTANT_PRIVATE_CORPUS_MANIFEST` at that manifest and list
the corpus folder in `ASSISTANT_PRIVATE_CORPUS_DIRS`; an entry that resolves outside those
folders stops the build.

Every build records `git describe` of this repository and of the corpus repository in the
`assistant_collections` table, so a measurement can name the exact code and corpus behind it:

```bash
docker exec become-assistant-db psql -U assistant -d assistant -c "SELECT name, corpus_version, app_version, chunk_count FROM assistant_collections"
```

## Running the pgvector-backed tests locally

`tests/integration/api/test_assistant_store.py`, `test_assistant_pipeline.py` and
`test_assistant_retrieval.py` run against a real, throwaway PostgreSQL cluster that
`pytest-postgresql` starts on the `pg_ctl` found on `PATH` - Homebrew's `postgresql@16`,
not the `assistant-db` container above. Without the `vector` extension next to that
`postgresql@16`, these tests skip with a clear reason instead of running.

Homebrew's own `pgvector` formula only builds against `postgresql@17`/`postgresql@18`, not
the `@16` this project pins, so `brew install pgvector` will not help here. Build it from
source against the right `pg_config` instead, following pgvector's own documented steps:

```bash
cd /tmp
git clone --branch v0.8.6 https://github.com/pgvector/pgvector.git
cd pgvector
export PG_CONFIG=/opt/homebrew/opt/postgresql@16/bin/pg_config
make
make install
```

`v0.8.6` matches the `pgvector/pgvector:0.8.6-pg16` image `assistant-db` runs, so a local
build and CI's `postgresql-16-pgvector` apt package exercise the same pgvector release.
Building this is optional: the tests above skip cleanly without it, and CI always has it
either way.

A `brew upgrade postgresql@16` can drop this hand-built extension along with it, so rebuild
it the same way after upgrading.
