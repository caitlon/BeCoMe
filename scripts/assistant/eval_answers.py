#!/usr/bin/env python3
"""Answer eval runner: put questions through the real chat service and record the answers.

Every question is one single-turn chat through ``POST /api/v1/assistant/chat``, so what is
measured is what a user gets: the service, the product prompt and the grounding checks.

The app is driven in-process (httpx's ASGI transport), with the fixtures user signed in by
a bearer token the way every route authenticates, so authorization and the tenant checks
run as in production. The mode is chosen through ``assistant_mode``: the service reads its
settings through a FastAPI dependency, and the runner overrides that one dependency with a
copy of the settings that carries the requested mode and has LangSmith tracing switched off.

Needs ``ASSISTANT_ENABLED=true`` and the model servers the settings point at; the runner
starts none. The database must hold the fixtures' user and projects. Set
``ASSISTANT_RATE_LIMIT_PER_HOUR=0`` for a long run: ``LIMIT_ASSISTANT_CHAT`` (20 a minute per
address) still applies.

The output holds answers and source titles; logs carry counts and timings only.
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
import langsmith as ls
import psycopg
from fastapi import FastAPI

from api.assistant.agent.prompt import SYSTEM_PROMPT
from api.assistant.rag.pipeline import git_version
from api.assistant.rag.retrieval import RetrievalConfig
from api.auth.jwt import create_access_token
from api.config import Settings, get_settings
from api.main import create_app

CHAT = "/api/v1/assistant/chat"

# sha256 of question files that are sealed: a run over one needs a written pre-registration.
SEALED_SHA256 = frozenset({"e9c434888f00c817f85a4e536c4ca8db3d551a13d6851bcb74ab806fb08b6559"})

PROMPT_SHA256 = hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()
REPO_ROOT = Path(__file__).resolve().parents[2]

# Consecutive turns without an answer after which the run stops: the environment is failing.
MAX_CONSECUTIVE_FAILURES = 3
# Statuses that are never a property of the answer, so the run stops at the first one.
_STOP_AT_ONCE = {
    "http_401": "the fixtures user was refused; check the user id in the fixtures file and "
    "that the user exists and is verified in the configured database",
    "http_429": "a rate limit is on; set ASSISTANT_RATE_LIMIT_PER_HOUR=0 for the hourly cap, or "
    "wait a minute for LIMIT_ASSISTANT_CHAT (20 a minute per address, it has no setting)",
}
# What must be equal across all rows of one arm for its rows to be comparable.
_PROVENANCE_FIELDS = (
    "mode",
    "prompt_sha256",
    "corpus_version",
    "app_version",
    "answer_model",
    "answer_endpoint",
    "retrieval_mode",
    "retrieval_query_transform",
    "retrieval_rerank",
    "retrieval_k",
    "answer_max_tokens",
    "query_model",
    "max_tool_calls",
    "collection",
    "code_version",
)


class RunRefusedError(Exception):
    """The run must not start; the message says why."""


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


def _load_questions(path: Path, project_keys: set[str]) -> list[dict[str, Any]]:
    """Read the questions and check them against the fixtures before any turn runs.

    :param path: JSONL file; each record has ``id`` and ``question``, and may have ``lang``
        and ``project`` (a fixtures key).
    :param project_keys: The keys the fixtures define.
    :return: The records, in file order.
    :raises ValueError: If a record is not a JSON object, lacks an id or a question, or names
        an unknown project key. The message names the line and the key, never the question.
    """
    records = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    for number, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raise ValueError(f"question record {number} is not a JSON object")
        if not record.get("id") or not record.get("question"):
            raise ValueError(f"question record {number} needs an id and a question")
        key = record.get("project")
        if key is not None and key not in project_keys:
            raise ValueError(f"question record {number} names the unknown project {key!r}")
    return records


def _read_rows(path: Path) -> list[dict[str, Any]]:
    """Read every row of an output file, oldest first.

    :param path: The output JSONL; it may not exist yet.
    :return: The rows, or an empty list.
    :raises RunRefusedError: If a line is not valid JSON, for instance a last line cut short
        by a crash, or is JSON but not an object with an ``id`` and an ``arm``; the message
        names the line.
    """
    if not path.exists():
        return []
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            raise RunRefusedError(f"{path}: line {number} is not valid JSON") from None
        if not isinstance(row, dict) or "id" not in row or "arm" not in row:
            raise RunRefusedError(f"{path}: line {number} is not an eval row")
        rows.append(row)
    return rows


def latest_rows(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    """Return the winning row per ``(id, arm)``: the last one written.

    A failed turn that was asked again with ``--retry-failed`` has two rows; the later wins.

    :param path: The output JSONL; it may not exist yet.
    :return: ``{(id, arm): row}``.
    """
    return {(row["id"], row["arm"]): row for row in _read_rows(path)}


def _stop_reason(status: str, consecutive: int) -> str | None:
    """Say why the run must stop after a turn, or None when it goes on.

    :param status: The status of the turn just written.
    :param consecutive: How many turns in a row, this one included, did not end ``ok``.
    :return: The message, or None.
    """
    again = "Rerun with --retry-failed to ask them again once the cause is fixed."
    if status in _STOP_AT_ONCE:
        return f"stopped at {status}: {_STOP_AT_ONCE[status]}. {again}"
    if consecutive >= MAX_CONSECUTIVE_FAILURES:
        return (
            f"stopped after {consecutive} turns in a row without an answer "
            f"(last status: {status}). {again} --retry-failed works only while the code version "
            "and settings are unchanged; after a code or settings fix, continue under a new "
            "--arm or a new --output."
        )
    return None


def _retrieval_config(settings: Settings) -> RetrievalConfig:
    """Return the retrieval settings the chat service searches with.

    It repeats what ``deps.get_docs_retriever`` builds; a test compares the two.

    :param settings: The application settings.
    :return: The config.
    """
    return RetrievalConfig(k=settings.assistant_retrieval_k)


def _provenance_problem(rows: list[dict[str, Any]], meta: dict[str, Any]) -> str | None:
    """Name the fields in which this run differs from the rows its arm already holds.

    :param rows: Every row of the output file.
    :param meta: This run's row metadata.
    :return: A message listing the differing fields, or None when the arm is consistent.
    """
    same_arm = [row for row in rows if row["arm"] == meta["arm"]]
    differing = [
        field
        for field in _PROVENANCE_FIELDS
        if any(row.get(field) != meta[field] for row in same_arm)
    ]
    if not differing:
        return None
    return (
        f"the output holds rows of arm {meta['arm']!r} made under a different "
        f"{', '.join(differing)}; use another --arm or output file"
    )


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
    http: httpx.AsyncClient, record: dict[str, Any], project_id: str | None, user_id: str
) -> dict[str, Any]:
    """Run one single-turn chat and return its result fields.

    The access token is minted for this question: it lives 15 minutes and a run lasts longer.

    :param http: The in-process client.
    :param record: The question record.
    :param project_id: The id of the project the question is asked about, or None.
    :param user_id: The fixtures user's id.
    :return: ``status``, ``latency_s`` and, for an answered turn, the response fields.
    """
    body: dict[str, Any] = {"message": record["question"]}
    if project_id is not None:
        body["project_id"] = project_id
    result: dict[str, Any] = {"answer": None, "sources": None, "tool_calls": None, "checks": None}
    started = time.monotonic()
    try:
        token = create_access_token(UUID(user_id))
        response = await http.post(CHAT, json=body, headers={"Authorization": f"Bearer {token}"})
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
    code_version: str | None,
    retry_failed: bool = False,
) -> dict[str, Any]:
    """Ask the questions one after another and append one row per question to ``output``.

    Every row already in ``output`` for the same id and arm counts as done, whatever its
    status: a failed turn is a result. With ``retry_failed`` those whose latest row is not
    ``ok`` are asked again, and the new row wins (:func:`latest_rows`). The run stops when
    :func:`_stop_reason` says the environment is failing. While it lasts the app's settings
    dependency is overridden with :func:`_eval_settings` and tracing is off; the override is
    removed afterwards.

    :param app: The FastAPI app with the assistant router mounted.
    :param questions: The records from :func:`_load_questions`.
    :param fixtures: The loaded fixtures.
    :param settings: The application settings, for the row metadata.
    :param arm: A free label written into every row.
    :param mode: ``workflow``, ``hybrid`` or ``agent``.
    :param output: The JSONL file rows are appended to.
    :param versions: ``(app_version, corpus_version)`` the collection's registry records.
    :param code_version: The version of the code that generates the answers.
    :param retry_failed: Ask again the questions whose latest row is not ``ok``.
    :return: ``rows`` written, ``ok`` and ``failed`` counts, ``median_latency_s``, ``unresolved``,
        how many of this arm's pairs have a non-``ok`` latest row in the whole file, and ``stop``,
        the message of the rule that ended the run early, or None.
    :raises RunRefusedError: If the arm's existing rows were made under other settings.
    """
    projects = _project_ids(fixtures)
    retrieval = _retrieval_config(settings)
    meta = {
        "arm": arm,
        "mode": mode,
        "answer_model": settings.assistant_answer_llm_model,
        "answer_endpoint": _endpoint(settings.assistant_answer_llm_base_url),
        "retrieval_mode": retrieval.mode,
        "retrieval_query_transform": retrieval.query_transform,
        "retrieval_rerank": retrieval.rerank,
        "retrieval_k": retrieval.k,
        "answer_max_tokens": settings.assistant_answer_max_tokens,
        "query_model": settings.assistant_llm_model,
        "max_tool_calls": settings.assistant_max_tool_calls,
        "collection": settings.assistant_collection,
        "app_version": versions[0],
        "corpus_version": versions[1],
        "code_version": code_version,
        "prompt_sha256": PROMPT_SHA256,
    }
    problem = _provenance_problem(_read_rows(output), meta)
    if problem is not None:
        raise RunRefusedError(problem)
    done = {
        key
        for key, row in latest_rows(output).items()
        if not (retry_failed and row["status"] != "ok")
    }
    todo = [record for record in questions if (record["id"], arm) not in done]
    output.parent.mkdir(parents=True, exist_ok=True)
    run_settings = _eval_settings(settings, mode)
    user_id = str(fixtures["user"]["id"])
    app.dependency_overrides[get_settings] = lambda: run_settings
    ok = consecutive = 0
    stop: str | None = None
    latencies: list[float] = []
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://eval.invalid",
        ) as http:
            # The query-transform call runs before the service's own tracing scope opens.
            with ls.tracing_context(enabled=False), output.open("a", encoding="utf-8") as sink:
                for number, record in enumerate(todo, start=1):
                    key = record.get("project")
                    result = await _ask(
                        http, record, None if key is None else projects[key], user_id
                    )
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
                    consecutive = 0 if result["status"] == "ok" else consecutive + 1
                    stop = _stop_reason(result["status"], consecutive)
                    if stop is not None:
                        break
    finally:
        app.dependency_overrides.pop(get_settings, None)
    unresolved = sum(
        row["status"] != "ok" for (_, row_arm), row in latest_rows(output).items() if row_arm == arm
    )
    return {
        "rows": len(latencies),
        "ok": ok,
        "failed": len(latencies) - ok,
        "median_latency_s": statistics.median(latencies) if latencies else None,
        "unresolved": unresolved,
        "stop": stop,
    }


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse CLI arguments for one answer eval run.

    :param argv: The arguments, or None for ``sys.argv``.
    :return: The parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", required=True, type=Path, help="Questions JSONL")
    parser.add_argument("--fixtures", required=True, type=Path, help="Fixtures JSON")
    parser.add_argument("--mode", required=True, choices=["workflow", "hybrid", "agent"])
    parser.add_argument("--arm", required=True, help="Free label written into every row")
    parser.add_argument("--output", required=True, type=Path, help="Output JSONL, appended to")
    parser.add_argument("--retry-failed", action="store_true", help="Ask failed questions again")
    parser.add_argument("--sealed-run", action="store_true", help="Allow a sealed question set")
    parser.add_argument("--registration", type=Path, default=None, help="Pre-registration file")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the eval and print the summary line.

    :param argv: The arguments, or None for ``sys.argv``.
    :return: The exit code: 0 on a finished run, 2 when the run is refused or misconfigured,
        3 when it stopped because the environment is failing.
    """
    args = _parse_args(argv)
    try:
        digest = hashlib.sha256(args.questions.read_bytes()).hexdigest()
    except OSError as exc:
        print(f"cannot read the questions: {exc}", file=sys.stderr)
        return 2
    problem = _seal_problem(digest, args)
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
        questions = _load_questions(args.questions, set(_project_ids(fixtures)))
    except (ValueError, KeyError, OSError) as exc:
        print(f"cannot read the inputs: {exc}", file=sys.stderr)
        return 2
    versions = _collection_versions(settings)
    missing = [
        name
        for name, value in zip(("app_version", "corpus_version"), versions, strict=True)
        if value is None
    ]
    if missing:
        names = " and ".join(missing)
        if args.sealed_run:
            print(
                f"a sealed run needs both of the collection's versions; missing from the "
                f"registry: {names}",
                file=sys.stderr,
            )
            return 2
        print(
            f"warning: {names} {'are' if len(missing) > 1 else 'is'} null in every row",
            file=sys.stderr,
        )
    try:
        summary = asyncio.run(
            run_eval(
                create_app(),
                questions,
                fixtures,
                settings=settings,
                arm=args.arm,
                mode=args.mode,
                output=args.output,
                versions=versions,
                code_version=git_version(REPO_ROOT),
                retry_failed=args.retry_failed,
            )
        )
    except RunRefusedError as exc:
        print(exc, file=sys.stderr)
        return 2
    median = summary["median_latency_s"]
    print(
        f"rows={summary['rows']} ok={summary['ok']} failed={summary['failed']} "
        f"median_latency_s={'n/a' if median is None else f'{median:.2f}'} "
        f"unresolved={summary['unresolved']}"
    )
    if summary["stop"] is not None:
        print(summary["stop"], file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
