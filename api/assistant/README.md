# Local assistant

Runs only on a developer machine. `Settings` refuses to start any deployed profile with
`ASSISTANT_ENABLED=true`.

## Contents

- [Prerequisites](#prerequisites)
- [Start](#start)
- [The chat endpoint](#the-chat-endpoint)
    - [Modes](#modes)
    - [Limits](#limits)
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
3. Model servers: `./scripts/assistant/run-llama-servers.sh` starts four: the small chat model
   for query transforms and index building (:8081, `ASSISTANT_LLM_*`), embeddings (:8082),
   rerank (:8083) and the answer model that writes chat answers (:8084,
   `ASSISTANT_ANSWER_LLM_*`, Qwen3.5-9B Q8_0). The answer model adds about 10 GB of memory and
   downloads on first start. `ASSISTANT_ANSWER_MAX_TOKENS` caps one answer and
   `ASSISTANT_RETRIEVAL_K` is how many passages the chat endpoint's search returns.
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
   `supplementary/assistant-eval/<collection>-<timestamp>.json`. Under
   `--query-transform translate_en`, English questions that the check recognises are searched as written and only
   non-English ones are translated, so reports for English questions are not directly
   comparable with reports made before this change.
6. Seed the data for questions about "my project": `uv run python
   scripts/assistant/seed_eval_fixtures.py --output supplementary/assistant-eval/fixtures.json`
   creates in the configured local database one activated user, `eval-owner@example.test`,
   who owns the product's example project (Floods case, 13 experts) and a second one built from
   the pendlers case study (22 experts, calculated). The password is `--password` or generated
   and printed once on stderr, as soon as the account exists. An existing account keeps its
   password, so `--password` has no effect on a rerun; a second run changes nothing and says
   "already present". The JSON (user id, and per project its key, id, name, expert count and
   result numbers) is what an evaluation run reads; the keys are listed in the script's docstring. It exits with 2 and
   touches nothing unless the profile is `dev` and the database is SQLite or on a loopback host.

   Answer evaluation: `scripts/assistant/eval_answers.py` asks every question of a JSONL file as
   one single-turn chat through the real chat route, in-process and as the user the fixtures
   file names, so authorization, the product prompt and the grounding checks run as they do for
   a user. A record has `id`, `question` and optionally `lang` and `project` (a fixtures key).
   Questions run one at a time, and each appends a row to `--output`: the record, `status`
   (`ok`, `http_<code>` or an exception name), `answer`, `sources`, `tool_calls`, `checks`,
   `latency_s`, a `timestamp` and what produced it: `arm`, `mode`, models, token and tool-call
   limits, retrieval settings, `collection`, `prompt_sha256` and `code_version`. `app_version`
   and `corpus_version` are the collection's own, from its registry row. A question file whose
   hash is on the sealed list is refused without `--sealed-run` and a non-empty
   `--registration` file, and a sealed run also needs those two versions.

   A rerun treats every row there for the same `id` and `arm` as done, whatever its status,
   because a failed turn is a result. `--retry-failed` asks again those whose latest row is not
   `ok`; the last row per `(id, arm)` wins (`latest_rows` returns them), and the summary's
   `unresolved` counts the arm's pairs still not `ok`. A run whose provenance fields differ from
   the arm's rows is refused with exit 2. After 3 turns in a row without an answer the run
   stops with exit 3, and at the first `http_401` or `http_429` at once; fix the cause, then
   rerun with `--retry-failed`. `ASSISTANT_RATE_LIMIT_PER_HOUR=0` suits a long run.

   ```bash
   uv run python scripts/assistant/eval_answers.py --questions questions.jsonl \
       --fixtures supplementary/assistant-eval/fixtures.json --mode workflow --arm 9b-workflow \
       --output supplementary/assistant-eval/answers.jsonl
   ```

   Grading the answers: `scripts/assistant/grade_answers.py` reads the latest row per question
   and arm from `--answers`, joins each to its question in `--questions` by `id` (records carry
   `id` and `lang`) and writes one grade per row to `--output`. No model runs and the grader
   reads no setting: the grades are checks on the text and on the row's own fields, so a rerun
   repeats them. It reads the rows through the runner's `latest_rows`, so it needs the
   environment the runner needs to import. A row whose turn failed is graded `completed: false`
   with null checks. The checks are the answer's language against the question's, the `[n]`
   citations used and how many name a source, and pseudo citations such as `[docs]` or
   `[Source 1]`; citations are read with `api/assistant/agent/checks.py`. The per-arm summary is
   printed, and `--summary` writes it as JSON.

   ```bash
   uv run python scripts/assistant/grade_answers.py \
       --answers supplementary/assistant-eval/answers.jsonl --questions questions.jsonl \
       --output supplementary/assistant-eval/grades.jsonl
   ```
7. Backend: set `ASSISTANT_ENABLED=true` in `.env`, then run the API as usual. This turns on
   `GET /api/v1/assistant/config` and `POST /api/v1/assistant/chat`
   (`api/routes/assistant.py`); the `model` field of the first reports the answer model.

## The chat endpoint

`POST /api/v1/assistant/chat` answers one question, as the signed-in user. It takes the same
session as every other route: the access cookie with the `X-CSRF-Token` header, or a bearer
token. The body is an `AssistantChatRequest` (`api/schemas/assistant.py`): `message`, an
optional `history` of earlier `user` and `assistant` turns, an optional `project_id` for the
project the user is looking at, and `locale` (`en` or `cs`). The answer carries the text, the
documentation `sources` it may cite as `[n]`, the `tools_used` and the grounding `checks`.

The assistant reads project data through the application's own API, with the caller's own
access token, so it sees exactly the projects the caller is a member of. What a project the
caller cannot see does depends on the mode. In `workflow` and `hybrid` the project named by
`project_id` is read ahead of the model, so the request is answered `404` exactly as
`GET /api/v1/projects/{id}` answers it. In `agent` mode nothing is read ahead: the request is
answered `200`, and a tool asked for such a project tells the model `not_found:` and nothing
else, so the answer says it found nothing. A failing model server, embedding server, vector
database or application answers `503` with a fixed message, including when the vector database
is down or its URL is not set on the first request after a start, and a spent message budget
`429`.

### Modes

`ASSISTANT_MODE` picks how a turn runs:

- `workflow` (the default): the code searches the documentation and, when the request names a
  project, reads the project, its result and its opinions, and the model answers once with no
  tools.
- `hybrid`: the code fetches the same, except the opinions, and the model may then call the
  tools.
- `agent`: nothing is fetched ahead; the model calls the tools, at most
  `ASSISTANT_MAX_TOOL_CALLS` times.

Two models take part. The answer model writes every answer; the small chat model
(`ASSISTANT_LLM_*`) only translates search queries, so the retriever is given that one.

### Limits

- **Message limit.** `ASSISTANT_RATE_LIMIT_PER_HOUR` messages per user in a fixed hour
  (default 60), counted in Redis when `REDIS_URL` is set and in memory otherwise. It is spent
  first, before the API client, the retriever or any model is built, so a message it refuses
  costs no model call; a message with an invalid body still spends one. Set it to `0` to switch
  it off, for a measurement run that sends many questions from one account.
- **Message length.** `ASSISTANT_MAX_MESSAGE_CHARS` (default 4000, which is also the ceiling of
  the request schema) can only lower the length of a message. A longer one is answered `422`
  like any other invalid request, before the API client is built, before the retriever is built
  and before any model call; it still spends one message of the hourly budget. A body the schema
  rejects (an unknown field, a message over 4000) is different: FastAPI keeps resolving the other
  dependencies after a body error, so the retriever may be built first, and on a cold start with
  the database down such a request answers `503`, not `422`.
- **Per-address limit.** `LIMIT_ASSISTANT_CHAT` (`20/minute`, `api/middleware/rate_limit.py`)
  applies to every address on top of that. It is checked inside the route, after the
  dependencies, so a message it refuses has already spent one hourly message and had an API
  client built and closed; it makes no model call.
- **Turn timeout.** `ASSISTANT_TURN_TIMEOUT_SECONDS` (default 180) bounds one turn, fetching and
  generation together; a turn that outlives it is answered `503`.

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
