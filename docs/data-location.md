# Where the data is processed

This page lists every service that handles data from BeCoMe, what it receives, where it runs, and
how that location was established. It is for the people who use the product and for anyone who
wants to check the claim that BeCoMe keeps data in the European Union. The claim holds for most
services and fails for two, which the page names. The facts were checked on 24 October 2026. The
[privacy notice](https://www.becomify.app/privacy) is the legal statement, and this page gives the
detail behind it.

## Contents

- [Services and regions](#services-and-regions)
- [What leaves the EU](#what-leaves-the-eu)
- [Assistant traces and the name mask](#assistant-traces-and-the-name-mask)
- [How the regions were checked](#how-the-regions-were-checked)

## Services and regions

Ekaterina Kuzmina is the controller. Each service below processes data on the controller's behalf.

| Service | What it receives | Where | How it was checked | Role |
|---|---|---|---|---|
| OVHcloud AI Endpoints | The assistant's model calls: the question, up to the last 20 messages of the conversation, document excerpts, and the project data, including member names, positions and values, except members who hid their opinions | EU, France | The API host resolves to an OVH SAS address in its Gravelines network. OVHcloud states that it runs the service in the EU, does not train models on the data and keeps only what billing needs. | Processor |
| Railway: backend, frontend, application database, the assistant's document database, Redis | Everything the application stores. Redis holds sessions, the revocation list, login throttles, rate-limit counters and a short-lived profile cache. | `europe-west4-drams3a`, which Railway lists as EU West, Amsterdam, Netherlands. The services and their data volumes are there, in all three environments. | Railway API: the deployment region and the volume region | Processor |
| Railway Bucket | Profile photos | Amsterdam | `railway bucket info` reports the bucket region. Where the storage endpoint itself runs was not checked. | Processor |
| Cloudflare (CDN, DNS, origin lock) | Every request to the site and the API: TLS, cookies, request bodies and photos | The edge nearest the visitor, worldwide. The Free plan has no regional restriction, since Regional Services is an Enterprise add-on. | Zone plan read through the API. The API refused the regional settings for this plan. | Processor |
| Cloudflare Turnstile (bot check on sign-in, registration, password reset and verification resend) | The challenge token, and the user's IP address when the backend knows it, sent to `challenges.cloudflare.com`. The widget runs in the browser and talks to Cloudflare directly. | Widget region `world` | Turnstile widget API | Processor |
| Resend | Recipient address, subject and body of verification and password-reset emails, so the links too | Mail is sent from AWS `eu-west-1` (Ireland). Resend states that it stores all account data, including email metadata, logs and API records, in the United States whatever the sending region. | The bounce (MX) record of the sending subdomain points to `feedback-smtp.eu-west-1.amazonses.com`, which follows the domain's sending region. The region setting itself could not be read through the API. Resend documentation for the storage location. | Processor |
| Sentry | Crash reports from the browser and the server, release-health session records, and about one request in ten as a performance trace | EU region, Frankfurt, Germany | The organization's region URL is `de.sentry.io` and the DSN ingest host is in the `de` region. Sentry documentation maps the EU region to Frankfurt. | Processor |
| Better Stack | Server logs, including IP addresses | EU data region `eu-central-1a`. Logs are kept for 3 days. | Source settings read through the Better Stack API | Processor |
| LangSmith (LangChain, Inc., a US company) | Assistant traces: the question, the history, the documents found, the opinions block, the model calls, the tool replies and the answer, with experts' names and positions masked | EU, GCP `europe-west4` (Netherlands). Traces are kept for 14 days. | The backend uses `eu.api.smith.langchain.com`, and its configuration refuses any other host on a deployed service. The trace tier `shortlived` is 14 days, read through the API. LangSmith documentation maps the EU instance to GCP `europe-west4`. Sign-in data for the EU instance sits in AWS `eu-central-1` (Germany). | Processor |

What the assistant sends to the model and to the trace store is described for users in
[What the assistant sends](user/security.md#what-the-assistant-sends). Why the model provider was
chosen is in [The model provider](assistant.md#the-model-provider).

## What leaves the EU

Two services handle data outside the EU, and a third is a US company that holds data in the EU.

Cloudflare handles each request at the data centre nearest to the visitor. The plan in use does
not keep that inside the EU. The bot check sends the user's IP address and the challenge token to
Cloudflare, and its widget region is `world`.

Resend sends mail from Ireland but keeps its account data, including message metadata and logs, in
the United States. This is Resend's statement about its own storage.

LangChain, Inc. is a US company. It stores the traces in the EU, and it may access them from the
United States under the EU standard contractual clauses in its data processing agreement. The
privacy notice says the same.

## Assistant traces and the name mask

Each assistant turn is recorded as a trace in LangSmith. Before a trace leaves the backend, a mask
replaces the names and positions of the project's experts with labels such as `Expert 1`. The
mask knows the names and positions as they are stored in the project. Its roster includes every
expert of the project the turn is about, also members who objected to the assistant.

A name is replaced as the whole name and as each of its words, in the Czech case forms and without
diacritics. A position is replaced only as the whole phrase.

These pass unmasked:

- typos, diminutives and nicknames
- forms that change the stem of the word, such as Kupka and Kupce
- a position that the model translates into the question's language or paraphrases
- a few words of a long position, quoted alone
- names of people who are not experts of that project
- a name inside an e-mail address, where a short lower-case part stays
- in a project of more than 100 experts, the names of the rest outside the opinions block
- everything that is not an expert's name or position: the question's own text, the project
  description and the documents

The full list, with the edge cases, is in the
[tracing section of the assistant's README](https://github.com/caitlon/BeCoMe/blob/prod/api/assistant/README.md#tracing).

## How the regions were checked

Where a live interface exists, the region was read from it: the provider's API, the command-line
tool, or DNS. Where only the provider can say, as with where Resend stores its account data or
what OVHcloud keeps, the provider's own documentation was used. The "How it was checked" column
shows which of the two each row rests on. The facts hold on the date at the top of the page, and a
provider can move a region later.
