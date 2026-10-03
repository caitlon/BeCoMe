#!/usr/bin/env python3
"""Answer eval runner: put questions through the real chat service and record the answers.

Earlier lab scripts called the model directly with a prompt of their own. This runner asks
every question as one single-turn chat through ``POST /api/v1/assistant/chat``, so what is
measured is what a user gets: the service, the product prompt and the grounding checks.

The app is driven in-process (httpx's ASGI transport), with the fixtures user signed in by
a bearer token the way every route authenticates, so authorization and the tenant checks
run as in production. The mode is chosen through ``assistant_mode``: the service reads its
settings through a FastAPI dependency, and the runner overrides that one dependency with a
copy of the settings that carries the requested mode and has LangSmith tracing switched off.

    uv run python scripts/assistant/eval_answers.py \\
        --questions questions.jsonl --fixtures fixtures.json \\
        --mode workflow --arm 9b-workflow --output answers.jsonl

Needs ``ASSISTANT_ENABLED=true`` and the model servers the settings point at; the runner
starts none. The database the app is configured with must hold the fixtures' user and
projects (the seeding script writes the fixtures file). Set ``ASSISTANT_RATE_LIMIT_PER_HOUR=0``
for a long run: ``LIMIT_ASSISTANT_CHAT`` (20 a minute per address) still applies.

The output file holds answers and source titles, so it is written only where it is pointed.
Logs carry counts and timings, never a question or an answer.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

import httpx
import psycopg
from fastapi import FastAPI

from api.assistant.agent.prompt import SYSTEM_PROMPT
from api.auth.jwt import create_access_token
from api.config import Settings, get_settings
from api.main import create_app

CHAT = "/api/v1/assistant/chat"

# sha256 of question files that are sealed: a run over one needs a written pre-registration.
SEALED_SHA256 = frozenset({"e9c434888f00c817f85a4e536c4ca8db3d551a13d6851bcb74ab806fb08b6559"})

PROMPT_SHA256 = hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    """Return the sha256 hex digest of a file's bytes.

    :param path: The file to hash.
    :return: The digest.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _seal_problem(digest: str, args: argparse.Namespace) -> str | None:
    """Say why a questions file may not be run, or None when it may.

    :param digest: sha256 of the questions file.
    :param args: Parsed arguments; ``sealed_run`` and ``registration`` are read.
    :return: A message, when the file is sealed and the run lacks ``--sealed-run`` or a
        registration that exists and is not empty; otherwise None.
    """
    if digest not in SEALED_SHA256:
        return None
    if not args.sealed_run:
        return "the questions file is sealed; pass --sealed-run with --registration <file>"
    registration: Path | None = args.registration
    if registration is None:
        return "a sealed run needs --registration <file>, the written pre-registration"
    if not registration.is_file() or registration.stat().st_size == 0:
        return "the registration file is missing or empty"
    return None


def _load_fixtures(path: Path) -> dict[str, Any]:
    """Read the fixtures file written by the seeding script.

    :param path: Path to the fixtures JSON.
    :return: ``{"user": {"id", "email"}, "projects": [{"key", "id", ...}]}``.
    :raises ValueError: If the user id or a project's key and id are missing.
    """
    fixtures: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    UUID(str(fixtures["user"]["id"]))
    for project in fixtures["projects"]:
        if not project.get("key") or not project.get("id"):
            raise ValueError("every fixtures project needs a key and an id")
    return fixtures


def _project_ids(fixtures: dict[str, Any]) -> dict[str, str]:
    """Map each fixtures project key to its id.

    :param fixtures: The loaded fixtures.
    :return: ``{key: id}``.
    """
    return {project["key"]: project["id"] for project in fixtures["projects"]}


def _load_questions(path: Path, project_keys: set[str], limit: int | None) -> list[dict[str, Any]]:
    """Read the questions and check them against the fixtures before any turn runs.

    :param path: JSONL file; each record has ``id`` and ``question``, and may have ``lang``
        and ``project`` (a fixtures key).
    :param project_keys: The keys the fixtures define.
    :param limit: Keep only the first N records, or all when None.
    :return: The records, in file order.
    :raises ValueError: If a record lacks an id or a question, or names an unknown project
        key. The message names the line and the key, never the question.
    """
    records = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    for number, record in enumerate(records, start=1):
        if not record.get("id") or not record.get("question"):
            raise ValueError(f"question record {number} needs an id and a question")
        key = record.get("project")
        if key is not None and key not in project_keys:
            raise ValueError(f"question record {number} names the unknown project {key!r}")
    return records if limit is None else records[:limit]


def _done(output: Path) -> set[tuple[str, str]]:
    """Return the ``(id, arm)`` pairs an earlier run already wrote.

    :param output: The output JSONL; it may not exist yet.
    :return: The finished pairs.
    """
    if not output.exists():
        return set()
    rows = (json.loads(line) for line in output.read_text(encoding="utf-8").splitlines() if line)
    return {(row["id"], row["arm"]) for row in rows}


def _eval_settings(settings: Settings, mode: str) -> Settings:
    """Copy the settings with the requested mode and LangSmith tracing off.

    Tracing sends the full text of questions and answers to a remote service, so the runner
    never leaves it on, whatever the environment says.

    :param settings: The application settings.
    :param mode: ``workflow``, ``hybrid`` or ``agent``.
    :return: The settings the service runs under.
    """
    return settings.model_copy(
        update={"assistant_mode": mode, "assistant_langsmith_enabled": False}
    )


def _collection_versions(settings: Settings) -> tuple[str | None, str | None]:
    """Read the configured collection's app and corpus version from the registry.

    :param settings: The application settings.
    :return: ``(app_version, corpus_version)``; ``(None, None)`` when the database URL is
        not set, the database cannot be reached, or the collection has no registry row.
    """
    url = settings.assistant_vector_db_url
    if not url:
        return None, None
    dsn = url.replace("postgresql+psycopg://", "postgresql://")
    try:
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            row = conn.execute(
                "SELECT app_version, corpus_version FROM assistant_collections WHERE name = %s",
                (settings.assistant_collection,),
            ).fetchone()
    except psycopg.Error:
        return None, None
    return (row[0], row[1]) if row is not None else (None, None)


def _endpoint(base_url: str) -> str:
    """Return ``host:port`` of a URL, without any credentials.

    :param base_url: The answer model's base URL.
    :return: ``host:port``, or just the host when the URL names no port.
    """
    parts = urlsplit(base_url)
    host = parts.hostname or ""
    return f"{host}:{parts.port}" if parts.port else host


def _row_from_response(body: dict[str, Any]) -> dict[str, Any]:
    """Pick what a row records from a successful chat response.

    :param body: The decoded ``AssistantChatResponse``.
    :return: The answer, sources (with whether each has a url), tool names and checks.
    """
    return {
        "answer": body["answer"],
        "sources": [
            {
                "n": source["n"],
                "title": source["title"],
                "section": source["section"],
                "layer": source["layer"],
                "has_url": source["url"] is not None,
            }
            for source in body["sources"]
        ],
        "tool_calls": body["tools_used"],
        "checks": body["checks"],
    }


async def _ask(
    http: httpx.AsyncClient, record: dict[str, Any], project_id: str | None
) -> dict[str, Any]:
    """Run one single-turn chat and return its result fields.

    :param http: The in-process client, signed in as the fixtures user.
    :param record: The question record.
    :param project_id: The id of the project the question is asked about, or None.
    :return: ``status``, ``latency_s`` and, for an answered turn, the response fields.
    """
    body: dict[str, Any] = {"message": record["question"]}
    if project_id is not None:
        body["project_id"] = project_id
    if record.get("lang") in ("en", "cs"):
        body["locale"] = record["lang"]
    result: dict[str, Any] = {"answer": None, "sources": None, "tool_calls": None, "checks": None}
    started = time.monotonic()
    try:
        response = await http.post(CHAT, json=body)
    except Exception as exc:
        result["status"] = type(exc).__name__
    else:
        if response.status_code == 200:
            result["status"] = "ok"
            result.update(_row_from_response(response.json()))
        else:
            result["status"] = f"http_{response.status_code}"
    result["latency_s"] = round(time.monotonic() - started, 3)
    return result


async def run_eval(
    app: FastAPI,
    questions: list[dict[str, Any]],
    fixtures: dict[str, Any],
    *,
    settings: Settings,
    arm: str,
    mode: str,
    output: Path,
    versions: tuple[str | None, str | None],
) -> dict[str, Any]:
    """Ask the questions one after another and append one row per question to ``output``.

    Rows already in ``output`` for the same id and arm are skipped. While the run lasts the
    app's settings dependency is overridden with :func:`_eval_settings`; the override is
    removed afterwards.

    :param app: The FastAPI app with the assistant router mounted.
    :param questions: The records from :func:`_load_questions`.
    :param fixtures: The loaded fixtures.
    :param settings: The application settings, for the row metadata.
    :param arm: A free label written into every row.
    :param mode: ``workflow``, ``hybrid`` or ``agent``.
    :param output: The JSONL file rows are appended to.
    :param versions: ``(app_version, corpus_version)`` of the collection.
    :return: ``rows`` written, ``ok`` and ``failed`` counts and ``median_latency_s``.
    """
    projects = _project_ids(fixtures)
    done = _done(output)
    todo = [record for record in questions if (record["id"], arm) not in done]
    run_settings = _eval_settings(settings, mode)
    meta = {
        "arm": arm,
        "mode": mode,
        "answer_model": settings.assistant_answer_llm_model,
        "answer_endpoint": _endpoint(settings.assistant_answer_llm_base_url),
        "retrieval_k": settings.assistant_retrieval_k,
        "app_version": versions[0],
        "corpus_version": versions[1],
        "prompt_sha256": PROMPT_SHA256,
    }
    token = create_access_token(UUID(str(fixtures["user"]["id"])))
    previous = app.dependency_overrides.get(get_settings)
    app.dependency_overrides[get_settings] = lambda: run_settings
    ok = 0
    latencies: list[float] = []
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://eval.invalid",
            headers={"Authorization": f"Bearer {token}"},
        ) as http:
            with output.open("a", encoding="utf-8") as sink:
                for number, record in enumerate(todo, start=1):
                    key = record.get("project")
                    result = await _ask(http, record, None if key is None else projects[key])
                    row = {
                        "id": record["id"],
                        "question": record["question"],
                        "lang": record.get("lang"),
                        "project": key,
                        **result,
                        **meta,
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                    sink.write(json.dumps(row, ensure_ascii=False) + "\n")
                    sink.flush()
                    ok += result["status"] == "ok"
                    latencies.append(result["latency_s"])
                    print(
                        f"turn {number}/{len(todo)}: {result['status']} in {result['latency_s']}s"
                    )
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_settings, None)
        else:
            app.dependency_overrides[get_settings] = previous
    return {
        "rows": len(latencies),
        "ok": ok,
        "failed": len(latencies) - ok,
        "median_latency_s": statistics.median(latencies) if latencies else None,
    }


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse CLI arguments for one answer eval run.

    :param argv: The arguments, or None for ``sys.argv``.
    :return: The parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", required=True, type=Path, help="Questions JSONL")
    parser.add_argument("--fixtures", required=True, type=Path, help="Fixtures JSON")
    parser.add_argument(
        "--mode", required=True, choices=["workflow", "hybrid", "agent"], help="Assistant mode"
    )
    parser.add_argument("--arm", required=True, help="Free label written into every row")
    parser.add_argument("--output", required=True, type=Path, help="Output JSONL, appended to")
    parser.add_argument("--limit", type=int, default=None, help="Ask only the first N questions")
    parser.add_argument(
        "--sealed-run", action="store_true", help="Allow a run over a sealed question set"
    )
    parser.add_argument(
        "--registration",
        type=Path,
        default=None,
        help="The written pre-registration, for a sealed run",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the eval and print the summary line.

    :param argv: The arguments, or None for ``sys.argv``.
    :return: The exit code: 0 on a finished run, 2 when the run is refused or misconfigured.
    """
    args = _parse_args(argv)
    problem = _seal_problem(_sha256_file(args.questions), args)
    if problem is not None:
        print(problem, file=sys.stderr)
        return 2
    settings = get_settings()
    if not settings.assistant_enabled:
        print(
            "set ASSISTANT_ENABLED=true: the chat route is not mounted without it", file=sys.stderr
        )
        return 2
    try:
        fixtures = _load_fixtures(args.fixtures)
        questions = _load_questions(args.questions, set(_project_ids(fixtures)), args.limit)
    except (ValueError, KeyError, OSError) as exc:
        print(f"cannot read the inputs: {exc}", file=sys.stderr)
        return 2
    summary = asyncio.run(
        run_eval(
            create_app(),
            questions,
            fixtures,
            settings=settings,
            arm=args.arm,
            mode=args.mode,
            output=args.output,
            versions=_collection_versions(settings),
        )
    )
    median = summary["median_latency_s"]
    print(
        f"rows={summary['rows']} ok={summary['ok']} failed={summary['failed']} "
        f"median_latency_s={'n/a' if median is None else f'{median:.2f}'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
