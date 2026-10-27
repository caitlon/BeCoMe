# Assistant

Runs on a developer machine; the validator also allows it on the Railway `dev`, `test` and `prod`
services. `Settings` refuses to start any other Railway environment with `ASSISTANT_ENABLED=true`,
and on a deployed service, the `prod` profile included, it requires all three model roles to be
`api`.

On the dev, test and prod services every model role runs hosted: `ASSISTANT_ANSWER_PROVIDER`,
`ASSISTANT_LLM_PROVIDER` and `ASSISTANT_EMBEDDING_PROVIDER` are `api`, each base URL is the OVH
endpoint, and `ASSISTANT_API_KEY_OVH` holds the key. LangSmith tracing is allowed there
only to the EU endpoint, into a named project other than the local default, and through
`ASSISTANT_LANGSMITH_ENABLED` alone: `LANGSMITH_TRACING` and its `LANGCHAIN_` variants, and
`LANGSMITH_RUNS_ENDPOINTS` and `LANGCHAIN_RUNS_ENDPOINTS`, are refused on a deployed service. A
deployed service needs an image built with the `assistant` extra and a corpus database reachable
through `ASSISTANT_VECTOR_DB_URL`. `env/.env.dev.example`, `env/.env.test.example` and
`env/.env.prod.example` list the variables.

How the pipeline is built and why, from the corpus to the streamed answer, is explained in
[How the assistant works](../../docs/assistant.md). This file covers running it.

## Contents

- [Prerequisites](#prerequisites)
- [Start](#start)
- [Model providers](#model-providers)
- [The chat endpoint](#the-chat-endpoint)
    - [Modes](#modes)
    - [Streaming](#streaming)
    - [Limits](#limits)
    - [Tracing](#tracing)
- [Private corpus layer](#private-corpus-layer)
- [Read-only role for a deployed corpus database](#read-only-role-for-a-deployed-corpus-database)
    - [Refreshing the corpus on a deployed service](#refreshing-the-corpus-on-a-deployed-service)
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
   downloads on first start. `ASSISTANT_ANSWER_MAX_TOKENS` caps one answer,
   `ASSISTANT_QUERY_MAX_TOKENS` (default 2048) caps one reply of the small model, which writes
   query transforms and also the context sentences and summaries at index time; it bounds a
   runaway reply, and a model that thinks inline needs a higher value. `ASSISTANT_RETRIEVAL_K`
   is how many passages the chat endpoint's search returns.
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
   who owns the product's example project (Floods case, 13 experts) and a second one built
   from the pendlers case study (22 experts, calculated). The password is `--password`, or
   the script asks for it (hidden) when it has to create the account; an empty answer, or no
   terminal to ask on, exits with 2 and creates no account. An existing account keeps its
   password and is not asked again, so `--password` has no effect on a rerun; a second run
   changes nothing and says "already present". The JSON (user id, and per project its key,
   id, name, expert count and result numbers) is what an evaluation run reads; the keys are
   listed in the script's docstring. It exits with 2 and touches nothing unless the profile
   is `dev` and the database is SQLite or on a loopback host.

   Answer evaluation: `scripts/assistant/eval_answers.py` asks every question of a JSONL file as
   one single-turn chat through the real chat route, in-process and as the user the fixtures
   file names, so authorization, the product prompt and the grounding checks run as they do for
   a user. A record has `id`, `question` and optionally `lang` and `project` (a fixtures key).
   Questions run one at a time, and each appends a row to `--output`: the record, `status` (`ok`,
   `http_<code>` or an exception name), `answer`, `sources`, `tool_calls`, `checks`, `latency_s`,
   `usage` (the turn's five usage fields, `null` on a failed turn), `timing` (the server's own
   `ttft_ms` and `total_ms`, `null` on a failed turn; `ttft_ms` is `null` unless the turn was
   streamed), a `timestamp` and what produced it: `arm`, `mode`, models, token and tool-call limits,
   retrieval settings, `collection`, `prompt_sha256`, `code_version` and `transport`. `app_version`
   and `corpus_version` are the collection's own, from its registry row. A question file whose hash
   is on the sealed list is refused without `--sealed-run` and a non-empty `--registration` file,
   and a sealed run also needs both versions and a clean checkout: a null in either version, or a
   `code_version` that is null or ends in `-dirty`, exits 2. An ordinary run prints a warning when
   either version is null.

   A rerun treats every row there for the same `id` and `arm` as done, whatever its status,
   because a failed turn is a result. `--retry-failed` asks again those whose latest row is not
   `ok`; the last row per `(id, arm)` wins (`latest_rows` returns them), and the summary's
   `unresolved` counts the arm's pairs still not `ok`. A run whose provenance fields differ from
   the arm's rows is refused with exit 2; the fields are listed in `_PROVENANCE_FIELDS` in the
   script, and their values come from the settings in `api/config.py` (models, the answer
   endpoint, token and tool-call limits, retrieval, collection), `SYSTEM_PROMPT` in
   `api/assistant/agent/prompt.py`, the collection's registry row (the two versions) and
   `git describe` (`code_version`). After 3 turns in a row without an answer the run stops with
   exit 3, and at the first `http_401` or `http_429` at once; fix the cause, then rerun with
   `--retry-failed`. After a 401 or 429 that works, since fixing either changes none of those
   fields. After a code or settings fix, `--retry-failed` is refused as soon as one of them
   changed; under a new `--arm` or a new `--output` the questions are asked again from the
   start. The route's per-address limit (`LIMIT_ASSISTANT_CHAT`, `<n>/minute`) is handled by
   pacing: the runner starts at most `n - 1` questions in any 60 s and prints the figure on
   stderr at the start; the wait is not part of `latency_s`. `--no-pacing` turns it off, for a
   rig where the limiter is off. The hourly caps are not paced: a long run still needs
   `ASSISTANT_RATE_LIMIT_PER_HOUR=0` and, since the pacing sends about 1140 questions an hour,
   `ASSISTANT_GLOBAL_TURNS_PER_HOUR=0` as well. Tracing is off unless `--trace` is given and
   `ASSISTANT_LANGSMITH_ENABLED` is on; it sends the question and answer text to LangSmith, with
   the names and positions of the project's experts replaced first (see [Tracing](#tracing)).
   In the running service, with the setting on, one chat turn is one trace: an `assistant_turn`
   run holding the query translation, the document search and the answer calls. In the agent
   mode the search shows as the tool call instead. The trace reaches LangSmith only when the
   turn ends.

   `--stream` asks `POST /api/v1/assistant/chat/stream` instead of `/chat` and reads its events,
   so the rows carry a first-token time, except in the agent and hybrid modes, which yield the
   whole answer at once and leave `ttft_ms` null. A turn whose stream ends in an `error` event has
   the status `stream_error_<code>`, and a body that ends with neither `done` nor `error` has
   `stream_incomplete`; a refusal before the stream opens is an `http_<code>` as on `/chat`. A
   `/chat` body that is not valid JSON is recorded with the status `JSONDecodeError`. It is a failed
   turn like any other, so three in a row still stop the run.
   The transport (`stream` or `chat`) is a row's `transport` field and a provenance field, so
   a file already holding rows of an arm over one transport refuses the other under that arm;
   rows written before the field existed count as `chat`. The runner prints
   `transport: stream` or `transport: chat` on stderr at the start, next to the pacing line.
   The pacing, the retry rules and the stop rules are the same for both.

   ```bash
   uv run python scripts/assistant/eval_answers.py --questions questions.jsonl \
       --fixtures supplementary/assistant-eval/fixtures.json --mode workflow --arm 9b-workflow \
       --output supplementary/assistant-eval/answers.jsonl
   ```

   Grading the answers: `scripts/assistant/grade_answers.py` reads the latest row per question
   and arm from `--answers`, joins each to its question in `--questions` by `id` (records carry
   `id` and `lang`, and optionally `answerable`, `project`, `expected_numbers`, a list of
   numbers, `needs_opinions`, `block` and `style`) and writes one grade per row to `--output`,
   which is overwritten. `block` and `style` are carried into the grade for later analysis and
   are not graded. The outputs are written only once every row is graded: a missing or empty
   answers file, or one with no row of a known question, exits 2 and leaves them alone, and so
   does an output path that is the answers file, the questions file or the other output, and a
   question record with a field of the wrong type. No model runs and the grader reads no
   setting: the grades are checks on the text and on the row's own fields, so a rerun repeats
   them. It reads the rows through the runner's `latest_rows`, so it needs the environment the
   runner needs to import. A row whose turn failed is graded `completed: false` with null
   checks. The checks are:

   - the answer's language against the question's (null when the answer is too short or has no
     function word to decide, which the summary counts as `lang_unknown`);
   - the `[n]` citations used and how many name a source, and pseudo citations: brackets such
     as `[Source 1]`, `[Zdroj 2]`, `[docs]`, `[data]` or `[project_data]`, while `[TODO]` or
     `[Q1-Q3]` are ordinary text;
   - how many expected numbers the answer states, as written, with a decimal comma, or rounded
     or truncated to one decimal (`numbers_recall`);
   - the numbers the chat service's own check flagged, and for an unanswerable question
     whether the answer states any number;
   - the share of local sources, and markdown;
   - for a question that `needs_opinions`, whether the opinions tool was called. In `workflow`
     mode, which has no tools, this is null.

   Numbers and citations are read with `api/assistant/agent/checks.py`. The per-arm summary is
   printed, and `--summary` writes it as JSON; its `missing` counts the questions with no row in
   that arm, so a run that stopped early does not read as complete. It also holds
   `median_ttft_ms`, the server's time from the model call to the first piece, retrieval
   excluded, over the completed rows whose `timing.ttft_ms` is not null (null for a run over
   `/chat`, and for `--stream` in the agent and hybrid modes, which yield the whole answer at
   once), next to `median_latency_s`, the client's whole-request time.
   Also in it are `median_input_tokens`, `median_output_tokens`, `median_total_tokens` and
   `median_llm_calls` over the completed rows that carry `usage`, and `usage_rows`, the number
   of those rows. The medians include rows whose usage is a partial sum, and `usage_incomplete`
   says how many of the `usage_rows` are such. `paired_bootstrap` gives the mean paired
   difference of two arms with a percentile interval over resampled questions, the same for a
   given seed.

   ```bash
   uv run python scripts/assistant/grade_answers.py \
       --answers supplementary/assistant-eval/answers.jsonl --questions questions.jsonl \
       --output supplementary/assistant-eval/grades.jsonl
   ```
7. Backend: set `ASSISTANT_ENABLED=true` in `.env`, then run the API as usual. This turns on
   `GET /api/v1/assistant/config`, `POST /api/v1/assistant/chat` and
   `POST /api/v1/assistant/chat/stream` (`api/routes/assistant.py`); the `model` field of the
   first reports the answer model. Like the chat routes, the config route needs a signed-in
   session. An anonymous request is answered `401`.

## Model providers

All three model roles run on local llama-servers by default. Each can instead use a hosted
OpenAI-compatible endpoint, switched on its own: `ASSISTANT_ANSWER_PROVIDER`,
`ASSISTANT_LLM_PROVIDER` (the query model) and `ASSISTANT_EMBEDDING_PROVIDER`, each `local` or
`api`. A role set to `api` sends its requests to that role's base URL
(`ASSISTANT_ANSWER_LLM_BASE_URL`, `ASSISTANT_LLM_BASE_URL`, `ASSISTANT_EMBEDDING_BASE_URL`),
so point the URL at the provider, OVHcloud's AI Endpoints being the EU one, and set the model
name to match. `Settings` refuses to start when an `api` role has no `ASSISTANT_API_KEY_OVH`,
a base URL that is not an `https://` URL of the provider's OpenAI-compatible endpoint (the
validator checks the scheme and the host, not the path), or a loopback host.

An `api` role sends the question text and the earlier turns of the conversation to the
provider, together with the documentation
excerpts retrieved for it, which can come from the private corpus layer as well as the public
documentation. In `agent` and `hybrid` modes the model also receives the project
data its tools read as the signed-in user, and that data goes to the provider too. In
`workflow` mode the answer role receives the project's details, result and opinions
(`AssistantService._fetch`). Building the index with an `api` embedding role sends the corpus
text to the provider. With a hosted query-model role, the context modes `llm_context` and
`doc_summary` of the index build (`pipeline.py`, `enrich`) also send corpus text to the
chat provider. The owner accepted this on the grounds that the provider is EU-resident and
bound by a data processing agreement (DPA). A role left `local` sends nothing off the machine.

The key is read from the environment only, held as a secret, and never logged, returned by
`GET /api/v1/assistant/config` or written to the evaluation rows. In `api` mode the two chat
models also send `reasoning_effort`, set by `ASSISTANT_API_REASONING_EFFORT` (`none` by
default; an empty value sends nothing): measured on OVHcloud, Qwen3.5-9B otherwise spends
every token on reasoning and returns no text. The reranker has no hosted counterpart and
always stays local. The config endpoint, which answers `401` without a session, reports
`answer_provider`, `query_provider` and `embedding_provider`, and the answer-evaluation runner
records the same three in each row, so rows made on different providers are never mixed in one
output file.

## The chat endpoint

`POST /api/v1/assistant/chat` answers one question, as the signed-in user. It takes the same
session as every other route: the access cookie with the `X-CSRF-Token` header, or a bearer
token. The body is an `AssistantChatRequest` (`api/schemas/assistant.py`): `message`, an
optional `history` of earlier `user` and `assistant` turns, an optional `project_id` for the
project the user is looking at, and `locale` (`en` or `cs`). The answer carries the text, the
documentation `sources` it may cite as `[n]`, the `tools_used`, the grounding `checks` and the
token `usage` of the turn. Each source carries a `snippet`, the first words of the passage in
plain text, at most 240 characters.

`ASSISTANT_SHOW_SOURCES` (off by default; meant to be enabled on dev and test through an
environment variable) decides whether the client is sent the sources. While it is off, `sources` is
an empty list, the answer text has no `[n]` marker and no link target after one, and
`checks.citations_valid` is always true, in `/chat` and in every event of `/chat/stream`. The
blanks before a marker go with it, except that a marker opening a line keeps the indent before it
and drops the blanks after it. A bracket that writes one number (`[7]`, `[source 2]`) is always
removed, even when no such source exists. A bracket that writes several numbers or a range
(`[1, 2]`, `[1-3]`) is removed only when each number in it is a source of the turn, so a fuzzy
number such as `[6, 8, 11]` or `[5, 5, 5]`, or a scale such as `[0, 1]`, stays. A bracket whose
whole content is the name of an internal tag or tool, which the model sometimes writes as if it
were a source, is removed the same way. Such names are `[project_data]`, `[project result]`,
`[tool result]`, `[System Instruction]`, the tool names such as `[search_docs]` or
`[get_project_result]`, and bare words such as `[source]`, `[docs]`, `[data]` or `[zdroj]`, in any
case and with `_`, `-` or blanks between words. The list is fixed, so other bracketed words such as
`[a_ij]` or `[TODO]` stay, and so does a name written as the text of a markdown link,
`[docs](https://...)`, with its link. Removal does not look at code spans, so a name inside
backticks goes too. A bracket inside a bracket is taken first, so `[[1]2]` goes whole. Numbered
citations are read as the citation check reads them, so a form that check does not recognise, such
as the full-width dagger form `【1†source】`, stays in the text; the internal names are known only to
the removal, not to the citation check or the history clean-up. The stream holds a piece back while
a marker may still be forming in it, and a bracket that never closes holds the rest of the answer
until the end, so a marker is never sent in part. The checks still run on the text the model wrote,
and the system prompt is the same in both states.

The assistant reads project data through the application's own API, with the caller's own
access token, so it sees exactly the projects the caller is a member of. Those internal reads
count against the caller's own rate-limit bucket: when `CLOUDFLARE_ORIGIN_SECRET` is set, the
client sends `X-Origin-Verify`, and the in-process transport's peer address is the caller's key.
The header never leaves the process.
What a project the caller cannot see does depends on the mode. In `workflow` and `hybrid` the
project named by `project_id` is read ahead of the model, so the request is answered `404`
exactly as `GET /api/v1/projects/{id}` answers it. In `agent` mode nothing is read ahead: the
request is answered `200`, and a tool asked for such a project tells the model `not_found:`
and nothing else, so the answer says it found nothing. A failing model server, embedding server,
vector database or application answers `503` with a fixed message. On any request until the
retriever has been built once, that covers a vector database that is down, a URL that is not set,
and a collection that is missing or that the role cannot read. Requests that arrive together on a
cold process each open an engine and fail or succeed on their own, so a database that is down does
not queue them; one retriever is kept and the other engines are closed. A model, embedding or rerank
server that answers `200` with a body that is no reply (an HTML page from a proxy, an `error`
object, no `choices` or `results`, an item of `data` without a vector or of `results` without
its `index` and `relevance_score`, a body that is empty or cut off, a stream chunk that is not
valid JSON, is cut inside a character, or is a JSON object of the wrong shape) is a failing
server too. A stream chunk that is valid JSON but not an
object is not caught and ends in a `500`. The warning for such a `503`
(`assistant_dependency_unavailable`, and `assistant_tool_unavailable` for a tool) carries the
class of the error as `reason` and the server that failed as `role`: `answer` or `query` for the
two chat models, `embedding`, `rerank`, `vector_db` for the document index, `app_api` for the
application, or `unknown` when nothing tagged the failure. The
code that talks to a server writes the role on the exception (`roles.py`); the text of an error is
never read for it. A spent message budget answers `429`.

The backends are also checked once when the process starts, in a background task, so the app
serves at once and a failed check never stops the start or changes `/health`. Each of the answer
model, the embedding server and the document index gets one small real request, the query model
and the reranker only when the retrieval config uses them. A failing one is logged at `ERROR` as
`assistant_backend_check_failed` with the same `role` as above and the class of the error as
`reason`, never its text; a probe that exceeds `ASSISTANT_LLM_TIMEOUT_SECONDS` has reason
`TimeoutError`. The document-index probe builds the retriever and keeps it, so the corpus
database pool is open from startup. Its `reason` is `AssistantUnavailableError`, and the
underlying class is on the `assistant_dependency_unavailable` warning logged just before it.
When all pass, `assistant_backends_checked` records the count and the time in milliseconds. Test
runs skip the check.

### Modes

`ASSISTANT_MODE` picks how a turn runs:

- `workflow` (the default): the code searches the documentation and, when the request names a
  project, reads the project, its result and its opinions, and the model answers once with no
  tools.
- `hybrid`: the code fetches the same, except the opinions, and the model may then call the
  tools.
- `agent`: nothing is fetched ahead; the model calls the tools, at most
  `ASSISTANT_MAX_TOOL_CALLS` times.

Whatever the mode, the model reads the opinions through `GET .../opinions?for_assistant=true`
(`UserApiClient.get_opinions`), which omits members who objected to the assistant (GDPR Art. 21,
`users.assistant_objection`) except the caller. The result block still counts them and includes
their values in the aggregates, so with a single objector their values follow from the aggregates
and the visible rows; the system prompt forbids the model to compute them and says the list can be
shorter than the number of experts. Only the trace mask reads the complete list
(`get_opinions(..., full=True)`).

In every mode the system prompt is the same constant. The code ends the turn's user message
with `Answer in Czech.` or `Answer in English.` only when the question is recognisably Czech
or English (`question_language` in `api/assistant/rag/retrieval.py`). A question in another
language, a mixed or very short one, or one that names a language anywhere gets no line, and
the system prompt's rule applies. A closely related language such as Slovak can be taken for
Czech.

Two models take part. The answer model writes every answer; the small chat model
(`ASSISTANT_LLM_*`) only translates search queries, so the retriever is given that one.

The answer model (`make_answer_model`) asks the server for usage on the last streamed chunk
(`stream_usage=True`), which a streamed turn needs for its token counts. `DirectGenerator.stream()`
yields the answer as it arrives, withholding any reasoning block, and its pieces always join to
the text `generate()` returns. `AgentGenerator.stream()` yields the whole answer once, since the
`hybrid` and `agent` modes do not stream.

The `usage` field of the response, `input_tokens`, `output_tokens`, `total_tokens`, `llm_calls`
and `complete`, adds up what the answer model's server reported for the replies of the turn:
the one reply in `workflow`, every reply of the tool loop and the extra call after a loop that
hit its limit in the other modes. It leaves out the query translation, which runs in the
retriever with the small chat model. `complete` is false when a reply reported no usage; its
tokens are then missing from the sums, though it still counts in `llm_calls`. The four numbers
are also on the `assistant_turn` log record, and so is `sources`, whatever `ASSISTANT_SHOW_SOURCES`
says: one entry per source the turn registered, with `n`, `title`, `section`, `layer` and
`cited` (whether the answer the model wrote cites it), and no excerpt, address or file path.

The `timing` field holds `ttft_ms`, the milliseconds from the start of the answer model's call to
its first piece of answer text, and `total_ms`, the whole turn with retrieval included. `ttft_ms`
is null unless the turn was streamed, which only `/chat/stream` does, and null for a streamed turn
in the `hybrid` and `agent` modes, which yield no text.

### Streaming

`POST /api/v1/assistant/chat/stream` takes the same body, session, CSRF header, message limit and
per-address limit as `/chat` and answers as `text/event-stream`, with `Cache-Control: no-cache` and
`X-Accel-Buffering: no`. Each event is a name line, one `data:` line of JSON and a blank line:

```
event: token
data: {"text":"It is the midpoint "}

event: done
data: {"answer":"It is the midpoint [1].","sources":[{...}],"tools_used":[],"checks":{...},"usage":{...},"timing":{"ttft_ms":412,"total_ms":2310}}

event: error
data: {"code":503,"detail":"The assistant is temporarily unavailable"}
```

`token` carries a piece of the answer and the pieces join to the answer in `done`, whose body is
what `/chat` returns. `error` ends the stream in place of `done`. The events above are those of
`ASSISTANT_SHOW_SOURCES` on; with it off the answer has no `[1]` and `sources` is `[]`.

Everything before the model is called is a plain HTTP error, as on `/chat`: retrieval runs before
the response opens, so a project the caller cannot see is `404`, an outage of the vector database
or the API, or a project API that answers something unusable, is `503`, a process already
answering its limit of turns is `503` with `Retry-After`, and a spent budget is `429`. After that
the status is already 200, so every failure arrives as an `error` event, with or without a token
before it: a model that is down, an empty or cut-off answer, a turn that outlives
its deadline (all `503`; the upstream-error branch is only defensive, since the tools catch an
unusable project API), and any other exception (`500`, `Internal server error`, logged as
`assistant_stream_failed` with the exception type and where it was raised, `file:line`). In the `hybrid`
and `agent` modes nothing streams: the body is the `done` event alone. `timing.ttft_ms` is measured from the
start of the model call, so it leaves out retrieval, and in the `hybrid` and `agent` modes it is null.

While the stream waits for the model's next piece, which in the `hybrid` and `agent` modes is
until the final response, it sends the comment block `: keep-alive` every
`ASSISTANT_STREAM_HEARTBEAT_SECONDS` (default 15, below 100), so that a proxy in front sees traffic;
Cloudflare answers `524` after 100 seconds without a byte. A block with no `event:` line carries no
event, and the frontend's parser skips it. A keep-alive is sent only between whole events, and the
`done` or `error` that ends the stream is unchanged.

A client that goes away stops the work its request started. During `/chat` and during the retrieval
that precedes a stream, the call in flight is cancelled and one `assistant_client_disconnected`
record at INFO names the route (`chat` or `chat_stream`) and the time in milliseconds; the turn
slot is given back, and no timeout or failure is logged. The response written for the vanished
client is an empty `499`, nginx's "client closed request", which nobody receives. Once a stream is
open the server cancels it when the client disconnects, with no record of this module. This relies
on the server reporting ASGI spec 2.3 (uvicorn 0.54 does, so Starlette's `StreamingResponse` listens
for the disconnect); on a server reporting 2.4 the vanished client is noticed at the next write, a
keep-alive at the latest. If the
watch for the disconnect itself fails, the turn runs on without it and
`assistant_disconnect_watch_failed` is logged at WARNING with the exception's class in `reason`.

### Limits

- **Message limit.** `ASSISTANT_RATE_LIMIT_PER_HOUR` messages per user in a fixed hour
  (default 60), counted in Redis when `REDIS_URL` is set and in memory otherwise. It is spent
  after the turn slot is taken and the request and the retriever are checked (see "Order of the
  checks" below), and before the API client or any model is built, so a message it refuses
  costs no model call. A Redis error does not lift it: each process then counts in its own
  memory with the same budget, and the record `assistant_throttle_unavailable` is logged at
  ERROR. Set it to `0` to switch it off, for a
  measurement run that sends many questions from one account; a deployed service refuses `0`.
- **Global ceiling.** `ASSISTANT_GLOBAL_TURNS_PER_HOUR` messages across all users together in a
  fixed hour (default 600), counted under the Redis key `assistant:chat:all` when `REDIS_URL` is
  set and in memory otherwise, with the same per-process fallback as the message limit. It is
  spent after the user's own budget, so an account whose budget is spent cannot drain it; a turn
  the ceiling refuses has therefore already spent one of that user's own hourly messages. A
  turn over the ceiling is `503`, the same body as an unreachable model server, with
  `Retry-After` set to the seconds until the window closes; the record
  `assistant_global_cap_reached` carries `reason: global` and no user. Set it to `0` to switch it
  off on a laptop; a deployed service refuses `0`.
- **Concurrent turns.** `ASSISTANT_MAX_CONCURRENT_TURNS` (default 8, above zero) is the most
  turns one process answers at once, and one user may run at most two of them, so a single account
  cannot take every slot. A turn that finds no free slot is refused at once, not queued, with `503`,
  the same body as an unreachable model server and `Retry-After: 5`; the record
  `assistant_concurrency_cap_reached` names the limit (`process` or `user`) and no user, and a
  refusal writes just that one. The slot is taken after the per-address limit and before the message
  limit, so a turn refused for a full process spends no message of the hourly budget, and a message
  the budget refuses gives its slot back at once. The slot is given back when the response is done,
  so a streamed answer holds it until the stream ends. The count is per process: with several
  processes the ceiling is the setting times their number.
- **Database session.** The chat routes look the caller up through their own dependency
  (`get_assistant_user` in `api/assistant/deps.py`), whose database session closes when the route
  function returns, before the body of a stream is sent. On a user-cache miss a stream therefore
  does not keep a connection of the application's pool checked out for the whole turn. Non-streamed
  `/chat` still holds the lookup's session for its whole turn, because the turn runs inside the
  route function; the frontend uses only `/chat/stream`.
- **Shutdown.** When the application stops with the assistant on, it closes what the process built:
  the corpus engine, the two chat models' clients and the throttles' Redis clients. Nothing is
  built only to be closed. A close that fails is recorded as `assistant_shutdown_close_failed`,
  with the resource and the error class, and the others still run. The embeddings client is not
  closed, because `OpenAIEmbeddings` gives no public way to close its underlying client. The
  reranker is not either: it opens a short-lived HTTP client for each call and holds none.
- **Message length.** `ASSISTANT_MAX_MESSAGE_CHARS` (default 4000, which is also the ceiling of
  the request schema) can only lower the length of a message. A longer one is answered `422`
  like any other invalid request, before the retriever is built, before the API client is built
  and before any model call, and it spends no message of the hourly budget. A body the schema
  rejects (an unknown field, a message over 4000) spends none either, but it is different in one
  respect: FastAPI keeps resolving the other dependencies after a body error, so the retriever
  may be built first, and on a cold start with the database down such a request answers `503`,
  not `422`.
- **Order of the checks.** The per-address limit, then the turn slot, then the request check and
  the retriever, then the hourly budget (the user's, then the global ceiling), and only after
  that the API client and the models. A request refused by any step before the budget spends no
  message: that covers `422` for an invalid body or a message that is too long, and `503` for a
  retriever that cannot be built (the vector database is down or not configured). The retriever
  is built once per process, so once it exists a request pays nothing for it. A failed build is
  not cached: on a process whose vector database is down, a caller over budget drives one
  retriever build attempt per request, bounded by the per-address limit and the turn slots, and
  gets `503`, not `429`.
- **Per-address limit.** `LIMIT_ASSISTANT_CHAT` (`20/minute`, `api/middleware/rate_limit.py`)
  applies to every address on top of that. It is the first dependency of both routes, checked
  before the turn slot, the session check and the message limit, so a message it refuses spends
  no hourly message, takes no slot and builds nothing. A request refused later for another
  reason, an unauthenticated one included, has already counted against it, and an anonymous
  request over the limit is answered `429`, not `401`. Each route has its own counter, so
  `/chat` and `/chat/stream` each allow `20/minute` per address, while the hourly message limit
  is shared by both.
- **Turn timeout.** `ASSISTANT_TURN_TIMEOUT_SECONDS` (default 180) bounds one turn, fetching and
  generation together; a turn that outlives it is answered `503`.
- **First-byte timeout.** `ASSISTANT_FIRST_BYTE_TIMEOUT_SECONDS` (default 90) bounds the work done
  before a response's first byte, and is kept under the 100 seconds after which Cloudflare
  answers `524` for an origin that has sent nothing. It is counted from the start of the turn's
  preparation, not from the request's arrival. It applies to the retrieval and project fetch that
  precede a stream and to the whole of a `/chat` turn, whose answer is one body. A turn that
  outlives it is answered `503` like any other, and the record `assistant_turn_timeout` names the
  limit that fired in `timeout_limit` (`first_byte` or `turn`). The streamed part of a turn keeps
  the full turn deadline. The setting can only shorten a turn: with a turn timeout below it, the
  turn timeout fires first. `/chat` fails at 90 seconds by default; set the variable above the
  turn timeout to restore the turn timeout as the only limit.

### Tracing

With `ASSISTANT_LANGSMITH_ENABLED` on, one chat turn is one LangSmith trace. The trace holds the
question, the history, the documents found, the opinions block, every model call, the tool
replies, the answer, the errors and the run metadata, with the turn's participants hidden.

The participants are the experts of every opinions list the turn fetched: the list `workflow`
mode reads ahead, the one the opinions tool returns, and, in every mode when the request names a
project, the project's complete opinions fetched for this purpose alone, before the model is
called. The complete list includes members who objected to the assistant, so a name the asker
types is masked too; the model never sees it. That fetch is cut off after five seconds, and a
failure or timeout does not change the turn but drops its trace (see below). Each expert gets
a label, `Expert 1`, `Expert 2` and so on, in order of first appearance. In the trace, a row of
the opinions block reads `- Expert 1: lower=...`, the label standing where the model read the
name and the position. In every other string of the trace:

- a name is replaced by the expert's label, as the whole name and as each of its words, in the
  Czech cases a word takes (Nováková, Novákové, Novákovou) and without diacritics (Novak). The
  whole name and any word of five letters or more match in any case of the first letter; a
  shorter word keeps the case it was written in. A word is replaced only as a whole word, so
  `Eva` is replaced and `evaluation`, `Evropa` and the verb `will` for an expert named `Will`
  are not;
- a position is replaced as a whole phrase, never word by word, by `[position of Expert 1]`, or
  by `[position]` when several experts hold it.

The runs of a turn are kept in memory and sent when the turn ends, because in `agent` mode the
question and the first model call start before any opinions are fetched. A worker thread of the
tracing client masks and sends them, so the work does not hold up other requests. A trace
appears in LangSmith only after the answer, a process that dies mid-turn loses that trace, and
so does shutdown for a turn still running; shutdown first finishes the traces already handed to
the worker. A call that belongs to no known turn is dropped and logged with
`reason=unknown_trace` (a call with no trace id is also logged once at WARNING); a call that
cannot be masked is dropped and logged with the exception class only. Neither is ever sent as
it is. A second layer masks any opinions block by its shape, whoever its rows name.

If the turn is about a project and its experts could not be read into the roster (the fetch
failed or timed out, in `workflow` mode the project read failed, or in `hybrid` mode any fetch
ahead failed, the document search included), the trace could miss a name, so it is dropped
whole, with one INFO record (`event=assistant_trace_dropped`, `reason=roster_incomplete`), and late
calls of the turn are dropped too, logged at DEBUG. A turn that names no project is sent.

What the mask misses: typos, diminutives, and forms that change the stem (Kupka, Kupce); a
position the model translates or paraphrases; a few words of a long position quoted alone (a
position is found only as a whole phrase); of a stranger's name that a block shows cut, a last
word of fewer than four letters and whatever the cut hid (the rest of a word, or the words after
it); a name inside an e-mail
address, where a lower-case word of fewer than five letters stays (a name stored as `Jana` is
matched only with its capital, so `jana.novakova@example.com` becomes
`jana.Expert 1@example.com`); a name in the history that belongs to a project the turn did not
fetch, unless it sits in an opinions block; and, in a project of more than 100 experts, the names
of the rest outside an opinions block (their rows are still masked). A run that ends after its
turn, for example when the client disconnects, is masked with the roster the turn had and sent
behind that turn's runs; past the last 256 turns it is dropped.

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

## Read-only role for a deployed corpus database

On a deployed service the backend reads the corpus as a role that can only select. Serving
issues no writes and no DDL: `open_store` reads the table's column list and every search is a
`SELECT`. The owner role does the writing, in `scripts/assistant/ingest.py`, which creates the
`vector` extension, the collection tables and the `assistant_collections` registry.

Create the role once, as the database owner. `<owner>` is the role that runs the ingest, and
`<database>` the corpus database:

```sql
CREATE ROLE corpus_reader LOGIN PASSWORD '<generated password>';
GRANT CONNECT ON DATABASE <database> TO corpus_reader;
GRANT USAGE ON SCHEMA public TO corpus_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO corpus_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE <owner> IN SCHEMA public GRANT SELECT ON TABLES TO corpus_reader;
```

The default privileges matter: every rebuild writes a new staging table and swaps it in under
the live name, so the live table is always a fresh one, and a plain `GRANT ... ON ALL TABLES`
covers only the tables that exist when it runs.

The backend's `ASSISTANT_VECTOR_DB_URL` is then
`postgresql+psycopg://corpus_reader:<password>@<private host>:5432/<database>?sslmode=require`.
`Settings` refuses a deployed service whose URL is empty, uses another driver than
`postgresql+psycopg`, names no database, carries a `host`, `hostaddr`, `port`, `dbname` or
`service` query parameter, names the application database, or lacks a single
`sslmode=require` (or `verify-ca`, `verify-full`).

Ingest runs from a developer machine, as the owner, through a temporary TCP proxy on the
database service. Remove the proxy afterwards.

Ingest embeds the corpus through the embedding settings, which default to the local
llama-server on `127.0.0.1:8082`. Point them at the provider for this run, so the corpus is
embedded by the same hosted model that embeds the questions. The registry row records the
embedding model id. `ASSISTANT_API_KEY_OVH` has to be set as well, in `.env` or the shell, and
so does `ASSISTANT_CAPTIONS_FILE`, because `--context captions` stops without it.

```bash
ASSISTANT_EMBEDDING_PROVIDER=api \
ASSISTANT_EMBEDDING_BASE_URL=https://oai.endpoints.kepler.ai.cloud.ovh.net/v1 \
ASSISTANT_EMBEDDING_MODEL=bge-m3 \
ASSISTANT_VECTOR_DB_URL='postgresql+psycopg://<owner>:<password>@<proxy host>:<proxy port>/<database>?sslmode=require' \
  uv run python scripts/assistant/ingest.py --name docs_markdown_headers_500_o10_captions_bge_m3 \
  --strategy markdown_headers --size 500 --overlap-pct 10 --context captions
```

The private corpus layer goes in with the same command once `ASSISTANT_PRIVATE_CORPUS_MANIFEST`
and `ASSISTANT_PRIVATE_CORPUS_DIRS` are set as described above.

Restart the backend after every reload. The order of the whole refresh, and why the restart
cannot be skipped, is in [Refreshing the corpus on a deployed service](#refreshing-the-corpus-on-a-deployed-service).

### Refreshing the corpus on a deployed service

Nothing does this automatically. No CI job and no deploy step reloads the corpus, so a change to
the documentation on its own leaves the deployed assistant answering from the old corpus until
someone follows these steps. The maintainer runs them by hand from a developer machine, once per
environment. They cover an environment that already has its corpus database and reader role; the
first setup is in the sections above and in `docs/environments.md`.

When: after a change to any source the corpus is built from reaches the environment's branch.
`build_manifest()` in `api/assistant/rag/corpus.py` is the reference for the file list:

- the pages under `docs/`, except `docs/security.md`, `docs/environments.md` and
  `docs/secrets.md` (`EXCLUDED_PUBLIC`); any other new page joins at the next ingest;
- the module READMEs those pages include by snippet (`docs/dev/*.md`, for example `api/README.md`
  and `src/README.md`), which the loader (`loaders.py`) pulls into the page when it loads it;
- the extra READMEs in `PUBLIC_EXTRA_READMES`;
- the `docs.json` and `faq.json` locale files under `frontend/src/i18n/locales/`;
- the private corpus repository.

Also refresh after a change to the chunker settings or to the corpus code itself: the lists in
`corpus.py` (`PUBLIC_EXTRA_READMES`, `EXCLUDED_PUBLIC`), `loaders.py`, `chunkers.py`,
`enrich.py` and `pipeline.py`, or to the embedding model.

On dev, refresh after the merge into `dev` and the backend deploy. On test and prod, refresh as
part of the promotion that carries the change, after that promotion's backend deploy. Build each
environment's corpus from a clean checkout that is up to date with `origin/<branch>` (`dev`,
`test` or `prod`). Then the corpus matches the documentation that environment serves, and
`app_version` carries no `-dirty` suffix. A fresh checkout has no `supplementary/` folder, and
`ASSISTANT_PRIVATE_CORPUS_MANIFEST`, `ASSISTANT_PRIVATE_CORPUS_DIRS` and `ASSISTANT_CAPTIONS_FILE`
resolve against the repository root unless they are absolute paths, so set them to absolute paths
there (`ASSISTANT_PRIVATE_CORPUS_DIRS` is a JSON list, `'["/abs/corpus"]'`).

1. Caption the new chunks, following [Refreshing captions after a corpus or chunker
   change](#refreshing-captions-after-a-corpus-or-chunker-change) through the commit of the
   captions file in the corpus repository, but skip `prune`. Captions that match no chunk cost
   nothing, because `enrich` ignores them. Dev usually holds chunks that test and prod do not
   have yet, so a `prune` from any one checkout drops captions another environment still needs.
   Run it only when dev, test and prod hold the same corpus sources. A caption is keyed by the
   chunk's text, so captions written once serve every environment whose chunks have the same
   text.
2. In the same checkout and the same shell environment as the ingest, run `uv run python
   scripts/assistant/captions.py missing --strategy markdown_headers --size 500 --overlap-pct 10`.
   It takes the chunking flags (`--strategy`, `--size`, `--overlap-pct`, `--wave`), not `--name`
   or `--context`. Without `ASSISTANT_CAPTIONS_FILE` it stops with an error; without the
   private-layer variables it checks only the public layer and can report `0` while private
   chunks have no caption. It prints `<missing> of <total>
   chunks have no caption; <stale> captions match no chunk`. The first count must be `0`; ignore
   the count after the semicolon, because `prune` is skipped. If some chunks are missing, the
   ingest builds them with only their title and prints "some chunks have no matching caption". If
   every chunk is missing, the ingest stops with an error and writes nothing.
3. Reload the environment's corpus database with the ingest command above, as the owner, through
   a temporary proxy. Then query the `assistant_collections` row of the deployed database as the
   owner: `psql 'postgresql://<owner>:<password>@<proxy host>:<proxy port>/<database>?sslmode=require'
   -c "SELECT name, created_at, chunk_count, corpus_hash, app_version, corpus_version FROM
   assistant_collections"`. `created_at` is the time of the reload, and it is the proof of it.
   `corpus_hash` is built from each source file's hash once per chunk, so it changes when a source
   text changes or the sources split into a different number of chunks, and not on a reload that
   only added captions. `app_version` and `corpus_version` name the two checkouts, so either
   stays the same when only the other repository changed. Remove the proxy.
4. Restart that environment's backend service. A restart is enough; no rebuild. The retriever is
   built once per process, and it builds its BM25 index from the collection's documents on the
   first search that needs one (`hybrid`, the default mode, and `bm25`). The build and every BM25
   scoring run in a worker thread, and concurrent first searches build one index. Ingest swaps the
   table under the same name, so dense search in a running process sees the new corpus at once.
   Only the BM25 index keeps the old chunks until the restart, and in `hybrid` mode the fused ranking
   then mixes new vectors with the old BM25 index.
5. Ask a question about the changed page and check that the answer comes from it.

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
   On a deployed service, follow [Refreshing the corpus on a deployed
   service](#refreshing-the-corpus-on-a-deployed-service) instead.

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
