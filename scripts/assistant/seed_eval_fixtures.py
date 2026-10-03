#!/usr/bin/env python3
"""Seed the local database with the accounts and projects an answer evaluation needs.

Questions about "my project" are answered from the signed-in user's own data, so an
evaluation run needs a user who owns known projects. This script creates that state
in the database the app's own settings point at, and prints what it created:

    uv run python scripts/assistant/seed_eval_fixtures.py [--password PW] [--output FILE]

It refuses to run (exit code 2) unless the profile is ``dev`` on a developer machine
and the database is SQLite or a loopback PostgreSQL. A second run changes nothing and
reports "already present" on stderr. The password comes from ``--password`` or is
generated, printed to stderr once on the run that creates the account, and never
written to stdout. An existing account keeps its password.

What a run creates, through the same services the product uses:

* one activated user, ``eval-owner@example.test`` (a reserved domain);
* the product's example project (Floods case, 13 experts), which ``ExampleProjectService``
  hands to every activated account. SQLite built by ``create_all`` has no pool of demo
  experts, so the missing pool accounts are inserted first, as the migration does;
* a second project from the pendlers case study (22 crisp Likert opinions from
  ``examples/data/pendlers_case.txt``), its experts synthetic demo accounts, calculated.

Output, one JSON document on stdout (or in ``--output``). The keys are stable::

    {
      "user": {"id": str, "email": str},
      "projects": [
        {
          "key": "example" | "pendlers",
          "id": str,
          "name": str,
          "expert_count": int,
          "result": {
            "best_compromise": {"lower": float, "peak": float, "upper": float,
                                "centroid": float},
            "arithmetic_mean": {same four keys},
            "median": {same four keys},
            "max_error": float,
            "num_experts": int,
            "agreement_level": "high" | "moderate" | "low",
            "likert_value": int | null,
            "likert_decision": str | null
          }
        }
      ]
    }

``projects`` always lists ``example`` first, then ``pendlers``. ``likert_*`` are the
values ``GET /projects/{id}/result`` returns: filled for a project on the plain 0-100
agreement scale, null otherwise.
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlmodel import Session, col, select

from api.auth.password import hash_password
from api.config import Environment, Settings, get_settings
from api.data.example_project import EXAMPLE_EXPERTS
from api.db.engine import _is_local_database, create_db_and_tables, get_engine
from api.db.models import CalculationResult, MemberRole, Project, ProjectMember, User
from api.db.utils import utc_now
from api.schemas.calculation import FuzzyNumberOutput
from api.schemas.project import ProjectCreate
from api.services.agreement_level import derive_agreement
from api.services.calculation_service import CalculationService
from api.services.example_project_service import ExampleProjectService
from api.services.likert_verdict import derive_verdict
from api.services.opinion_service import OpinionService
from api.services.project_service import ProjectService
from api.services.user_service import UserService
from examples.utils.data_loading import load_data_from_txt

OWNER_EMAIL = "eval-owner@example.test"
_OWNER_FIRST_NAME = "Eval"
_OWNER_LAST_NAME = "Owner"

PENDLERS_PROJECT_NAME = "Pendlers case (evaluation fixture)"
_PENDLERS_DATA = Path(__file__).resolve().parents[2] / "examples" / "data" / "pendlers_case.txt"
_PENDLERS_EXPERT_DOMAIN = "example.test"

_EXIT_REFUSED = 2


class UnsafeTargetError(Exception):
    """The configured profile or database is not a local development one."""


@dataclass
class SeedOutcome:
    """What one seeding run produced.

    :ivar payload: The JSON document described in the module docstring.
    :ivar created: Names of what this run created: ``user``, ``example``, ``pendlers``.
    :ivar generated_password: The password generated for a new account, if any.
    """

    payload: dict[str, Any]
    created: set[str] = field(default_factory=set)
    generated_password: str | None = None


def check_target(settings: Settings) -> None:
    """Refuse any target that is not a developer's own database.

    The profile must be ``dev``, the process must not be a deployed service or run on
    Railway, and the database must be SQLite or a loopback host (or Unix socket).

    :param settings: The app's settings.
    :raises UnsafeTargetError: If any of those does not hold.
    """
    if settings.environment is not Environment.DEV:
        raise UnsafeTargetError(
            f"profile is {settings.environment.value!r}; only the dev profile is allowed"
        )
    if settings.is_deploy or settings.railway_environment_name is not None:
        raise UnsafeTargetError("this process runs on a deployed service")
    if not _is_local_database(settings.database_url):
        raise UnsafeTargetError("the database is not SQLite or a loopback host")


def _ensure_demo_users(session: Session, users: list[User]) -> None:
    """Insert the demo accounts that are not in the database yet.

    :param session: Session to write through; this function commits.
    :param users: Demo accounts to add when their id is absent.
    """
    ids = [user.id for user in users]
    present = set(session.exec(select(User.id).where(col(User.id).in_(ids))).all())
    missing = [user for user in users if user.id not in present]
    if not missing:
        return
    # One hash for all of them: bcrypt costs ~0.2 s, and the plaintext is never kept.
    unusable = hash_password(secrets.token_urlsafe(64))
    for user in missing:
        user.hashed_password = unusable
        user.email_verified_at = utc_now()
        user.is_demo = True
        session.add(user)
    session.commit()


def _demo_pool_users() -> list[User]:
    """Build the example project's demo experts, as the migration seeds them.

    :return: Unsaved accounts, one per example expert.
    """
    return [
        User(
            id=expert.user_id,
            email=expert.email,
            hashed_password="",
            first_name=expert.first_name,
            last_name=expert.last_name,
        )
        for expert in EXAMPLE_EXPERTS
    ]


def _ensure_owner(session: Session, password: str | None) -> tuple[User, bool, str | None]:
    """Find the evaluation owner, or create and activate the account.

    :param session: Session to write through.
    :param password: Password for a new account; generated when None.
    :return: The account, whether this call created it, and the generated password
        when one was made.
    """
    service = UserService(session)
    existing = service.get_by_email(OWNER_EMAIL)
    if existing is not None:
        return existing, False, None
    chosen = password or secrets.token_urlsafe(16)
    user = service.create_user(
        email=OWNER_EMAIL,
        password=chosen,
        first_name=_OWNER_FIRST_NAME,
        last_name=_OWNER_LAST_NAME,
    )
    # Same end state as redeeming the activation link, which needs a mailed token.
    user.email_verified_at = utc_now()
    session.add(user)
    session.commit()
    session.refresh(user)
    return user, True, None if password else chosen


def _ensure_example_project(session: Session, owner: User) -> tuple[Project, bool]:
    """Find the owner's example project, or have the product's service create it.

    :param session: Session to write through.
    :param owner: The evaluation owner.
    :return: The project, and whether this call created it.
    """
    owned = ProjectService(session).get_owned_projects(owner.id)
    existing = next((p for p in owned if p.is_example), None)
    if existing is not None:
        return existing, False
    _ensure_demo_users(session, _demo_pool_users())
    created = ExampleProjectService(session).seed_for(owner.id)
    if created is None:
        raise RuntimeError("the example project was not created")
    return created, True


def _pendlers_expert_id(index: int) -> UUID:
    """Return the stable account id of the nth synthetic pendlers expert.

    :param index: One-based position of the expert in the case file.
    :return: A UUID derived from the expert's address, so reruns find the same account.
    """
    return uuid5(NAMESPACE_URL, _pendlers_expert_email(index))


def _pendlers_expert_email(index: int) -> str:
    """Return the reserved-domain address of the nth synthetic pendlers expert.

    :param index: One-based position of the expert in the case file.
    :return: The address.
    """
    return f"pendlers-expert-{index:02d}@{_PENDLERS_EXPERT_DOMAIN}"


def _ensure_pendlers_project(session: Session, owner: User) -> tuple[Project, bool]:
    """Find the owner's pendlers project, or build it from the case data.

    :param session: Session to write through.
    :param owner: The evaluation owner.
    :return: The project, and whether this call created it.
    """
    projects = ProjectService(session)
    owned = projects.get_owned_projects(owner.id)
    existing = next((p for p in owned if p.name == PENDLERS_PROJECT_NAME), None)
    if existing is not None:
        return existing, False

    opinions, metadata = load_data_from_txt(str(_PENDLERS_DATA))
    experts = [
        User(
            id=_pendlers_expert_id(index),
            email=_pendlers_expert_email(index),
            hashed_password="",
            first_name="Pendlers",
            last_name=f"Expert {index:02d}",
        )
        for index in range(1, len(opinions) + 1)
    ]
    _ensure_demo_users(session, experts)

    project = projects.create_project(
        owner.id,
        ProjectCreate(
            name=PENDLERS_PROJECT_NAME,
            description=metadata.get("description"),
            scale_min=0.0,
            scale_max=100.0,
        ),
    )
    opinion_service = OpinionService(session)
    for expert, opinion in zip(experts, opinions, strict=True):
        session.add(ProjectMember(project_id=project.id, user_id=expert.id, role=MemberRole.EXPERT))
        opinion_service.upsert_opinion(
            project.id,
            expert.id,
            opinion.expert_id,
            opinion.opinion.lower_bound,
            opinion.opinion.peak,
            opinion.opinion.upper_bound,
        )
    session.commit()
    CalculationService(session).recalculate(project.id)
    session.refresh(project)
    return project, True


def _result_payload(project: Project, result: CalculationResult) -> dict[str, Any]:
    """Shape a stored result as ``GET /projects/{id}/result`` reads it.

    :param project: Project the result belongs to, for its scale.
    :param result: The stored calculation.
    :return: The ``result`` object of the output document.
    """
    best = (
        result.best_compromise_lower,
        result.best_compromise_peak,
        result.best_compromise_upper,
    )
    verdict = derive_verdict(project, *best)
    return {
        "best_compromise": FuzzyNumberOutput.from_bounds(*best).model_dump(),
        "arithmetic_mean": FuzzyNumberOutput.from_bounds(
            result.arithmetic_mean_lower, result.arithmetic_mean_peak, result.arithmetic_mean_upper
        ).model_dump(),
        "median": FuzzyNumberOutput.from_bounds(
            result.median_lower, result.median_peak, result.median_upper
        ).model_dump(),
        "max_error": result.max_error,
        "num_experts": result.num_experts,
        "agreement_level": str(derive_agreement(project, result.max_error)),
        "likert_value": verdict.value if verdict else None,
        "likert_decision": verdict.decision if verdict else None,
    }


def _project_payload(session: Session, key: str, project: Project) -> dict[str, Any]:
    """Describe one seeded project for the output document.

    :param session: Session to read through.
    :param key: Stable short identifier, ``example`` or ``pendlers``.
    :param project: The project.
    :return: One entry of ``projects``.
    """
    result = CalculationService(session).get_result(project.id)
    if result is None:
        raise RuntimeError(f"project {key!r} has no calculation result")
    return {
        "key": key,
        "id": str(project.id),
        "name": project.name,
        "expert_count": len(OpinionService(session).get_opinions_for_project(project.id)),
        "result": _result_payload(project, result),
    }


def seed_fixtures(session: Session, password: str | None) -> SeedOutcome:
    """Create whatever of the evaluation state is missing, and describe all of it.

    :param session: Session to write through.
    :param password: Password for the owner when the account is created; generated
        when None. Ignored when the account exists.
    :return: The output document and what this run created.
    """
    owner, owner_new, generated = _ensure_owner(session, password)
    created = {"user"} if owner_new else set()
    example, example_new = _ensure_example_project(session, owner)
    pendlers, pendlers_new = _ensure_pendlers_project(session, owner)
    if example_new:
        created.add("example")
    if pendlers_new:
        created.add("pendlers")
    payload = {
        "user": {"id": str(owner.id), "email": owner.email},
        "projects": [
            _project_payload(session, "example", example),
            _project_payload(session, "pendlers", pendlers),
        ],
    }
    return SeedOutcome(payload=payload, created=created, generated_password=generated)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse the command line.

    :param argv: Arguments without the program name; None reads ``sys.argv``.
    :return: The parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--password", help="Password for the owner account (generated and printed when omitted)"
    )
    parser.add_argument("--output", type=Path, help="Write the JSON here instead of stdout")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Seed the fixtures and print the JSON document.

    :param argv: Arguments without the program name; None reads ``sys.argv``.
    :return: Exit code: 0 on success, 2 when the target is refused.
    """
    args = _parse_args(argv)
    settings = get_settings()
    try:
        check_target(settings)
    except UnsafeTargetError as error:
        print(f"Refusing to seed: {error}", file=sys.stderr)
        return _EXIT_REFUSED

    create_db_and_tables()
    with Session(get_engine()) as session:
        outcome = seed_fixtures(session, args.password)

    for name in ("user", "example", "pendlers"):
        state = "created" if name in outcome.created else "already present"
        print(f"{name}: {state}", file=sys.stderr)
    if outcome.generated_password is not None:
        print(f"generated password: {outcome.generated_password}", file=sys.stderr)

    document = json.dumps(outcome.payload, indent=2)
    if args.output is not None:
        args.output.write_text(document + "\n", encoding="utf-8")
    else:
        print(document)
    return 0


if __name__ == "__main__":
    sys.exit(main())
