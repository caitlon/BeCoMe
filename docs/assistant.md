# How the assistant works

The assistant answers two kinds of questions: how the BeCoMe method works, and what the result of
your own project means. This page explains how an answer is put together, from the documents the
assistant reads to the text that appears in the panel, and why each step is built the way it is.

It is written for anyone who wants to know what happens behind the panel. How to use the assistant
is on [The assistant](user/assistant.md), and what it sends about you and your project is in
[What the assistant sends](user/security.md#what-the-assistant-sends). How to run it on your own
machine is in the
[assistant's README](https://github.com/caitlon/BeCoMe/blob/prod/api/assistant/README.md).

## Contents

- [The path of one question](#the-path-of-one-question)
- [The documents it reads](#the-documents-it-reads)
- [How the documents are cut into passages](#how-the-documents-are-cut-into-passages)
- [How the search finds three passages](#how-the-search-finds-three-passages)
- [What the model sees of your project](#what-the-model-sees-of-your-project)
- [Why the code fetches the data instead of the model](#why-the-code-fetches-the-data-instead-of-the-model)
- [How the answer is written](#how-the-answer-is-written)
- [How citations and numbers are checked](#how-citations-and-numbers-are-checked)
- [How the answer streams](#how-the-answer-streams)
- [Sources on production and on the test environments](#sources-on-production-and-on-the-test-environments)
- [How the panel displays an answer](#how-the-panel-displays-an-answer)
- [Limits on use](#limits-on-use)
- [The model provider](#the-model-provider)
- [How the decisions were measured](#how-the-decisions-were-measured)

## The path of one question

The assistant is retrieval-augmented generation: it finds a few passages in its documents, hands
them to a language model together with your question, and asks the model to answer from them
alone. One question takes these steps:

1. The server checks that you are signed in, that the message fits the limits, and that you have
   messages left this hour.
2. If you asked from a project's panel, the server reads that project's data with your own access.
3. If the question is in Czech, a model translates it into English for the search.
4. The search finds the three passages that fit the question best.
5. One call to the language model writes the answer from the passages and the project data, and
   the answer streams to the panel as it is written.
6. When the answer is complete, the server checks its citations and numbers and sends the result
   with the last part of the stream.

The sections below explain these steps and the reasons behind them.

## The documents it reads

Everything the assistant knows about BeCoMe comes from a fixed set of documents, the corpus. It
has two layers.

The **public layer** is in this repository: the pages of this documentation site, the root
`README.md` and the READMEs of the examples, and the help and FAQ texts of the app in English and
Czech. Three engineering pages are left out on purpose: the security posture, the environment
setup, and the secrets runbook. They cover infrastructure and security detail rather than the
method or the app, and two of them are not published on this site either. This page is not left out. The assistant can read it, and it can answer "how
do you work?" from it.

The **local layer** holds published works that this repository does not redistribute: the article
that introduced the method, the bachelor thesis the app grew out of, and the papers behind the
flood case study and the aggregation theory. They are open access, but the files stay out of git.
Scanned books without a usable text layer, and pictures in general, are not indexed. Figures are
covered by the text that describes them.

The corpus lives in a separate PostgreSQL database with the pgvector extension, never in the app's
own database. The app's database is migrated on every deploy, and a corpus table that needs schema
rights should not sit next to user data. The running server reads the corpus with a read-only
role. Loading a new corpus is a manual step run by the maintainer. It builds the new collection in a
staging table and swaps it in one transaction, so a failed build leaves the old one in place.

## How the documents are cut into passages

Each document is cut at its headings (`#`, `##`, `###`), and a long section is cut further into
pieces of about 500 characters with a 10% overlap. Every passage keeps its heading path, such as
"How it works > Step 2", which is what a citation shows.

Twenty-two ways of cutting were measured on development questions, and nine of them tied on how
often the right passage was among the first five. Cutting at headings was chosen among the nine
because it is the one that keeps the section name. Semantic chunking, which cuts where the meaning shifts, came
last: it made few large passages and found the right one in about half of the questions.

Before a passage is indexed, a caption of one or two sentences is put in front of it, together with the
document's title. The caption says what the passage is about in plain English, so a passage that
only makes sense inside its section can still be found. The captions are written once, when the
corpus is prepared, by a larger commercial model than the one that answers. The running server
never calls it.

Captions were the strongest single improvement measured. With them, the right passage was among the
first five for 87% of the development questions instead of 73%. Captions written by a small local
model made the search worse, even when that model saw the whole document. The model that answers
sees each passage's own text, never its caption, so a caption cannot put words into an answer.

## How the search finds three passages

The search runs two methods side by side and merges their rankings.

- **Search by meaning.** Each passage is turned into a vector by `bge-m3`, a multilingual
  embedding model, and the question is compared with those vectors. `bge-m3` was compared with
  `Qwen3-Embedding-0.6B` and `multilingual-e5-large`. `Qwen3-Embedding-0.6B` with its standard
  instruction was slightly better on average, but `bge-m3` reached the best single setups and
  needs no instruction at all. `multilingual-e5-large` found almost none of the Czech questions.
- **Search by words.** BM25 ranks passages by the words they share with the question. It finds
  exact names and terms that the meaning search can miss.

The two rankings are merged by reciprocal rank fusion, which scores a passage by its position in
each list rather than by the raw scores. The merge runs in the app, not in PostgreSQL, because
PostgreSQL has no Czech text-search configuration.

Most documents are in English, so a word search for a Czech question finds nothing. A Czech
question is therefore translated into English before the search, by a model at temperature 0. A
question that already reads as English is searched as written. On a held-out set of 37 questions,
translation by a small local model raised the share of Czech questions with the right passage among
the first five from 80% to 95%. That small model has no host in the EU, so the deployed services
translate with `Qwen3.5-9B` instead, and with it the share is 85%. English questions gained nothing
from translation, so they skip it and save almost half a second.

The search returns three passages. In the measured setup, three passages held the right one for 95%
of the held-out questions, against 97% for five. Giving the model five passages did not make its answers more
complete. It only added claims that the passages do not support.

Two common additions were measured and left out:

- **A reranker**, a second model that reorders the candidates, improved the meaning search alone
  but barely changed the combined one. The reranker costs half a second to a second per question
  and has no host in the EU.
- **A hypothetical answer** used as the search query added nothing to the final setup and cost
  about two seconds per question.

The search uses your latest message on its own. A follow-up such as "and why is that?" is searched
as it stands, without the earlier turns, which is a known limit.

## What the model sees of your project

When you ask from a project's panel, the server reads that project before the model is called: its
name, description and scale, its result, and the opinions. It reads them through the app's own API,
with your access, so the assistant sees exactly what you see as a member of the project. It makes
read-only requests and cannot change anything. A project you cannot open is refused the same way
the app refuses it.

What reaches the model passes a list of allowed fields. Email addresses, account IDs and photos
are dropped. Each opinion carries the expert's name, position and values, and at most 50 opinions
are sent. A member who hid their opinions from other members' assistants is left out of the list
entirely, though the result still counts them. Names, positions and descriptions are typed by
users, so they are cleaned, shortened, and marked as data that the model must not follow as
instructions. Nobody has checked them, so the model reports them as what was entered in the
project, never as verified facts. The full list of what is sent is in
[What the assistant sends](user/security.md#what-the-assistant-sends).

Your earlier messages go along with the question, up to the last 20 and about 6,000 characters in
total. The server keeps no conversation history to answer from. The conversation lives in your
browser tab. Each turn is also kept in a trace record for 14 days, as
[What the assistant sends](user/security.md#what-the-assistant-sends) explains.

## Why the code fetches the data instead of the model

The assistant has three modes, set on the server, not by the user:

- `workflow`: the code runs the search and reads the project, and the model writes the answer in
  one call. This is the mode in use.
- `agent`: the model decides which tools to call. It can search the documents, list your
  projects, and read a project, its result and its opinions, with at most four tool calls per
  answer.
- `hybrid`: the `workflow` steps without the opinions, and the tools on top.

`workflow` is the only mode whose answers passed the evaluation. On a sealed set of 80 questions,
the `agent` mode delivered about a quarter of the facts that `workflow` did. It often answered that
the documents had nothing on the question, without having searched them. The `hybrid` mode never
called a tool on the development questions, so in practice it behaved like `workflow`. A model of
this size follows a fixed plan better than it makes one.

## How the answer is written

The answer comes from `Qwen3.5-9B`, an open-weight model, at temperature 0, with a limit of 800
tokens. The model's reasoning mode is switched off. With reasoning on, it spent the whole token
budget thinking and returned no visible text.

The instructions tell the model to state a fact only when a passage or the project data supports
it, to say so when it does not know, and never to compute a number itself. They also pin three
facts about the method that are easy to misread. One of them is that a small maximum error does
not mean the experts agree: every model tested made that mistake. The instructions also give the
agreement levels, which follow from the maximum error as a share of the scale width: up to 20% is
high and up to 40% is moderate.

The answer is in the language of the question. When the server is sure the question is Czech or
English, it adds a line that names the language, because the passages are mostly English and pull
the model towards English. When it is not sure, it adds nothing.

`Qwen3.5-9B` was chosen over the smaller `Qwen3-4B` after both answered the sealed set.
`Qwen3.5-9B` delivered more of the expected facts, and it put a claim not supported by the
passages in 26% of its answers, against 68% for `Qwen3-4B`. On 64 development questions,
`Qwen2.5-7B` and `EuroLLM-9B` did worse than `Qwen3.5-9B` on both counts. On the same questions,
putting the whole public documentation into the model's input instead of three passages was not
better either, and it used about 50 times as many input tokens.

The measurements also show where the limit lies. The right passage reaches the model for more than
nine questions in ten, yet on the sealed set the answers carried 47% of the expected facts. The
model that writes the answer is the weak step, not the search.

## How citations and numbers are checked

The model cites a passage as `[n]`. After the answer is written, the server runs two checks on it,
without calling any model.

- **Citations.** Every `[n]` must point at a passage the model was given. A citation to a passage
  that does not exist fails the check.
- **Numbers.** Every number in the answer must appear in the passages, in the project data, in
  your own messages, or among the few constants the instructions pin (the 20% and 40% thresholds
  and the divisors of the formulas). A rounded or shortened value counts as found: if the data
  says 14.19, an answer that says 14.2 passes.

A failed check does not block the answer and does not regenerate it. The answer arrives with a
flag, and the panel shows an orange warning under it: numbers not confirmed, or a citation that is
invalid. With sources hidden, as on production, only the number warning can appear. Answering
again would cost another model call and could fail the same way, while the warning tells you what
to verify. On the sealed set, 3% of the answers had a number the check
could not confirm, and 1% cited a passage that did not exist.

The number check has limits. It sees the numbers but not what they belong to, so a real number
attached to the wrong quantity passes. Numbers written as words are not checked.

## How the answer streams

The panel receives the answer as server-sent events. A `token` event carries the next piece of
text, and the stream ends with one `done` event that carries the whole answer, its sources and the
check results, or with an `error` event. The search and the project data are fetched before the
stream opens, so a refused request is an ordinary HTTP error and never a broken stream. Only
`workflow` streams text. In the other modes the whole answer arrives in the `done` event.

The site sits behind Cloudflare, which closes a connection that stays silent for 100 seconds. The
server therefore sends a keep-alive comment every 15 seconds. The work before the stream opens,
the search and the project data, must finish within 90 seconds, and the whole answer within 180.

## Sources on production and on the test environments

On the development and test environments, the answer shows its sources. With sources on, each
`[n]` becomes a link to a list under the answer, where every source shows its document title and section and opens a
short excerpt. A source from the local layer is marked as a local copy and has no link. A `[n]`
that points at no source is shown struck through.

Production does not show sources for now. The setting `ASSISTANT_SHOW_SOURCES` is off there, and it
works on the server, not only in the panel. The server removes the `[n]` markers from the answer,
also while it streams, and sends an empty list of sources, so no title or excerpt reaches the
browser at all. The search, the instructions and both checks stay the same. The citation flag is
always reported as valid there, because a warning about a link you cannot see would only confuse.
The server log still records which sources each answer used.

## How the panel displays an answer

The panel renders a small part of markdown: paragraphs, bold and italic text, lists, inline code
and line breaks. Headings, tables, images and links are reduced to their plain text, and raw HTML
is shown as text, never run. An answer therefore cannot place a link or a script in the page. The
only links in an answer are its own `[n]` markers, when sources are on. Your own messages are shown
as plain text.

## Limits on use

Any signed-in user can use the assistant. These limits keep one user, or a burst of users, from
exhausting the service:

| Limit | Value |
|---|---|
| Messages per user | 60 an hour |
| Requests per address | 20 a minute |
| Messages across all users | 600 an hour |
| Answers at the same time | 8 per server process, 2 per user |
| Length of one message | 4,000 characters |
| Tool calls per answer (`agent` and `hybrid` only) | 4 |
| Search and project data, before the stream opens | 90 seconds |
| Whole answer | 180 seconds |

A refused message gets a plain explanation in the panel, and a limit refusal says how long to wait.
The server never shows the text of an internal error.

## The model provider

All three model roles, the answer, the query translation and the embeddings, run at
[OVHcloud AI Endpoints](https://www.ovhcloud.com/en/public-cloud/ai-endpoints/). The service hosts
open-weight models behind the common chat completions API that most model hosts share, the same
request format that local model servers accept. The answer and the translation
use `Qwen3.5-9B`, and the embeddings use `bge-m3`.

OVHcloud was chosen because user data must stay in the EU. It was the only provider found that
serves these exact models from the EU, with terms that keep no questions or answers and do not use
them for training. Routers that pass requests on to compute mostly outside the EU were ruled out.
One answer uses about 1,000 tokens in total.

The server talks to the provider through LangChain's client for that API, on the
`/v1/chat/completions` and `/v1/embeddings` endpoints. Each role is configured separately, so each
one can point at the hosted API or at a model server on a developer's machine:

| Role | Provider setting | Model setting | Address setting |
|---|---|---|---|
| Answer | `ASSISTANT_ANSWER_PROVIDER` | `ASSISTANT_ANSWER_LLM_MODEL` | `ASSISTANT_ANSWER_LLM_BASE_URL` |
| Query translation | `ASSISTANT_LLM_PROVIDER` | `ASSISTANT_LLM_MODEL` | `ASSISTANT_LLM_BASE_URL` |
| Embeddings | `ASSISTANT_EMBEDDING_PROVIDER` | `ASSISTANT_EMBEDDING_MODEL` | `ASSISTANT_EMBEDDING_BASE_URL` |

On the deployed services every role is set to `api`, and all three addresses are
`https://oai.endpoints.kepler.ai.cloud.ovh.net/v1`. One key, `ASSISTANT_API_KEY_OVH`, serves all
three. It is sent only to a role set to `api`. When the assistant is switched on, the server
refuses to start a deployed service whose roles are not all hosted. Two details of the hosted API shape the code:

- `Qwen3.5-9B` reasons by default, and on this API it spends every token on reasoning. Each
  request therefore sends `reasoning_effort: "none"` (setting `ASSISTANT_API_REASONING_EFFORT`).
- The embeddings endpoint refuses more than 25 texts in one request, so the corpus is embedded in
  batches of 16.

On a developer's machine the same roles run on local llama.cpp servers. The hosted `bge-m3` gives
the same vectors as the local one, with a cosine similarity of at least 0.9997, so a corpus indexed
on either works with both. The hosted answer model delivered as many facts as the local one in
testing, but it made more claims that the passages do not support. It also varies between runs at
temperature 0: repeated, 18 of 32 answers came back word for word the same. Where the data goes
and who processes it is in [What the assistant sends](user/security.md#what-the-assistant-sends).

## How the decisions were measured

The numbers on this page come from evaluations run before each decision, with the rule for
accepting a change written down before the run.

- **Search** was tuned on 15 development questions and confirmed on 37 held-out questions, 17 in
  English and 20 in Czech, written without seeing any search results. A setup chosen as the best of
  hundreds on 15 questions can be among the worst on new ones, and one was. Defaults are therefore
  never picked on the development set alone.
- **Answers** were confirmed once on a sealed set of 80 questions, 42 in English and 38 in Czech,
  60 about the documents and 20 about a project. The set stayed locked until the rule was written,
  and nothing was tuned on it afterwards.
- **Judging** was done by language models that did not know which setup wrote which answer. They
  scored the share of expected facts delivered and the claims not supported by the sources. A
  second judge rescored a quarter of the answers to measure agreement.
- **Comparisons** use a paired bootstrap over the questions, so a difference counts only when its
  interval excludes zero.

The limits of this evidence matter as much as the numbers. It covers one corpus and one prompt
family, and the questions were written and judged by models. It shows which choice was better here.
It does not show how good the answers are in general.
