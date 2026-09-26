# Local assistant

Runs only on a developer machine. `Settings` refuses to start any deployed profile with
`ASSISTANT_ENABLED=true`.

## Contents

- [Prerequisites](#prerequisites)
- [Start](#start)
- [Private corpus layer](#private-corpus-layer)
- [Chunk captions](#chunk-captions)
    - [Refreshing captions after a corpus or chunker change](#refreshing-captions-after-a-corpus-or-chunker-change)
- [Running the pgvector-backed tests locally](#running-the-pgvector-backed-tests-locally)

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
4. Index the documentation: `uv run python scripts/assistant/ingest.py --name
   docs_markdown_headers_500_o10_captions_bge_m3 --strategy markdown_headers --size 500
   --overlap-pct 10 --context captions` builds the collection the backend reads by default;
   `--help` lists the chunker, context and wave options. Rerunning it with the same `--name`
   replaces that collection: the build writes into a staging table and swaps it in only once
   every chunk is stored, so a build that fails leaves the previous collection in place.
5. Evaluate retrieval quality: `uv run python scripts/assistant/eval_retrieval.py --collection
   docs_markdown_headers_500_o10_captions_bge_m3 --mode hybrid --query-transform translate_en`
   scores hit@1/3/5, MRR and nDCG@5 for that collection against the golden set
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

## Chunk captions

Prepending a short caption to a chunk's own text, before it is embedded, was the context
enrichment mode that improved retrieval quality the most, of everything this project's search
lab measured (`--context captions`, `api/assistant/rag/enrich.py`). A caption names the source
document and says what that one fragment covers, giving a generic-looking sentence the context
it would otherwise only have inside its full document.

Captions live in a JSON file, `chunk_key` (a chunk's own sha256, `enrich.py`) mapped to its
caption text, named by `ASSISTANT_CAPTIONS_FILE` and kept in the private corpus repository next
to the local manifest, so its own `git describe` becomes part of `corpus_version` the same way
the manifest's already does. Building a `captions` collection fails outright when none of its
chunks match an entry - a sign the file belongs to another corpus revision or chunker - and logs
a warning, by count only, when just some chunks miss one.

### Refreshing captions after a corpus or chunker change

1. `uv run python scripts/assistant/captions.py missing --strategy markdown_headers --size 500
   --overlap-pct 10 --out batch.json` chunks the corpus exactly as a real ingest run would,
   reports how many of its chunks have no caption yet and how many captions match no chunk at
   all, and, with `--out`, writes the documents that do - full text and all - to a JSON file.
   It touches only the corpus and the captions file: no chat model, no embedding server, no
   database.
2. Caption every fragment the batch file lists: one or two sentences, at most 50 words, naming
   what the document is and what that specific fragment covers - not a restatement of its own
   wording - written in English, with no markup. Save the result as a JSON object mapping each
   fragment's `sha` to its caption.
3. `uv run python scripts/assistant/captions.py merge <captioned-batch.json>` folds those
   captions into `ASSISTANT_CAPTIONS_FILE`, creating it on the first run, and reports how many
   captions were added versus replaced.
4. `captions.py prune`, with the same flags as `missing`, drops the captions whose fragment no
   longer exists. Pass the flags of the collection you build: under a different chunker or
   wave, captions that are still in use would count as stale. `missing` reports how many
   captions `prune` would drop, so run it first; `prune` refuses outright when not a single
   caption matches a fragment.
5. Commit the updated captions file in the corpus repository.
6. Rebuild the collection: rerun `ingest.py` (see "Start" above), so the new captions take effect.

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
