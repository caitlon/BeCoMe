"""Seeding an account with the worked example project.

The result is not stored as a constant: the service runs the real calculator over the
13 seeded opinions, so these tests double as a regression check that the seeded
numbers still produce the published Floods result.
"""

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from api.auth.password import hash_password
from api.data.example_project import EXAMPLE_EXPERTS, EXAMPLE_PROJECT_TEXT
from api.db.models import (
    CalculationResult,
    ExpertOpinion,
    MemberRole,
    Project,
    ProjectMember,
    User,
)
from api.services.example_project_service import ExampleProjectService
from tests.reference.floods_case import FLOODS_CASE
from tests.shared.helpers import insert_demo_experts

TOLERANCE = 1e-6


def _make_engine():
    """Build a fresh in-memory engine with the schema created."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def session():
    """In-memory SQLite session with the demo pool inserted."""
    engine = _make_engine()
    with Session(engine) as db_session:
        insert_demo_experts(db_session)
        yield db_session
    engine.dispose()


@pytest.fixture
def session_without_pool():
    """In-memory SQLite session whose demo pool was never inserted."""
    engine = _make_engine()
    with Session(engine) as db_session:
        yield db_session
    engine.dispose()


def _make_owner(session: Session, email: str = "owner@example.com") -> User:
    """Persist and return a freshly activated account."""
    user = User(
        email=email,
        hashed_password=hash_password("OwnerPassword1!"),
        first_name="New",
        last_name="Owner",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _insert_partial_demo_pool(session: Session, count: int) -> None:
    """Insert only the first ``count`` demo experts, as a half-applied migration would."""
    unusable_password = hash_password("UnusedPassword1!")
    for expert in EXAMPLE_EXPERTS[:count]:
        session.add(
            User(
                id=expert.user_id,
                email=expert.email,
                hashed_password=unusable_password,
                first_name=expert.first_name,
                last_name=expert.last_name,
                is_demo=True,
            )
        )
    session.commit()


@pytest.fixture
def owner(session):
    """The account the example is seeded into."""
    return _make_owner(session)


class TestSeedComposition:
    """What the seed writes."""

    def test_creates_one_example_project_owned_by_the_user(self, session, owner):
        """The owner is the admin, so the ordinary delete flow already works."""
        # GIVEN
        service = ExampleProjectService(session)

        # WHEN
        project = service.seed_for(owner.id)

        # THEN
        assert project is not None
        assert project.is_example is True
        assert project.admin_id == owner.id
        assert project.scale_min == 0.0
        assert project.scale_max == 100.0
        assert project.scale_unit == "%"

    def test_owner_joins_as_admin_and_the_pool_as_experts(self, session, owner):
        """14 memberships: the owner plus the 13 demo experts."""
        # GIVEN
        service = ExampleProjectService(session)

        # WHEN
        project = service.seed_for(owner.id)
        members = session.exec(
            select(ProjectMember).where(ProjectMember.project_id == project.id)
        ).all()

        # THEN
        assert len(members) == len(EXAMPLE_EXPERTS) + 1
        roles = {m.user_id: m.role for m in members}
        assert roles[owner.id] == MemberRole.ADMIN
        assert all(roles[e.user_id] == MemberRole.EXPERT for e in EXAMPLE_EXPERTS)

    def test_writes_one_opinion_per_expert(self, session, owner):
        """The owner's own opinion is deliberately not seeded."""
        # GIVEN
        service = ExampleProjectService(session)

        # WHEN
        project = service.seed_for(owner.id)
        opinions = session.exec(
            select(ExpertOpinion).where(ExpertOpinion.project_id == project.id)
        ).all()

        # THEN
        assert len(opinions) == len(EXAMPLE_EXPERTS)
        assert owner.id not in {o.user_id for o in opinions}

    def test_opinion_values_match_the_case_data(self, session, owner):
        """Each opinion carries its expert's triple and localized position."""
        # GIVEN
        service = ExampleProjectService(session)

        # WHEN
        project = service.seed_for(owner.id)
        opinions = {
            o.user_id: o
            for o in session.exec(
                select(ExpertOpinion).where(ExpertOpinion.project_id == project.id)
            ).all()
        }

        # THEN
        for expert in EXAMPLE_EXPERTS:
            stored = opinions[expert.user_id]
            assert stored.lower_bound == expert.lower_bound
            assert stored.peak == expert.peak
            assert stored.upper_bound == expert.upper_bound
            assert stored.position == expert.position_en


class TestSeedResult:
    """The calculation the seeded project opens with."""

    def test_result_matches_the_published_case(self, session, owner):
        """The engine reproduces the reference numbers from the seeded opinions."""
        # GIVEN
        service = ExampleProjectService(session)
        expected = FLOODS_CASE["expected_result"]

        # WHEN
        project = service.seed_for(owner.id)
        result = session.exec(
            select(CalculationResult).where(CalculationResult.project_id == project.id)
        ).first()

        # THEN
        assert result is not None
        assert result.num_experts == expected["num_experts"]
        assert result.best_compromise_lower == pytest.approx(
            expected["best_compromise_lower"], abs=TOLERANCE
        )
        assert result.best_compromise_peak == pytest.approx(
            expected["best_compromise_peak"], abs=TOLERANCE
        )
        assert result.best_compromise_upper == pytest.approx(
            expected["best_compromise_upper"], abs=TOLERANCE
        )
        assert result.max_error == pytest.approx(expected["max_error"], abs=TOLERANCE)

    def test_displayed_centroid_is_the_published_number(self, session, owner):
        """14.31 % on screen is the centroid of the compromise, not its peak."""
        # GIVEN
        service = ExampleProjectService(session)
        expected = FLOODS_CASE["expected_result"]

        # WHEN
        project = service.seed_for(owner.id)
        result = session.exec(
            select(CalculationResult).where(CalculationResult.project_id == project.id)
        ).first()
        centroid = (
            result.best_compromise_lower
            + result.best_compromise_peak
            + result.best_compromise_upper
        ) / 3

        # THEN
        assert centroid == pytest.approx(expected["best_compromise_centroid"], abs=TOLERANCE)


class TestSeedLanguage:
    """Which language the stored text is in."""

    def test_czech_language_seeds_czech_text(self, session, owner):
        """Name, description and every position come from the Czech set."""
        # GIVEN
        service = ExampleProjectService(session)

        # WHEN
        project = service.seed_for(owner.id, language="cs")
        opinions = session.exec(
            select(ExpertOpinion).where(ExpertOpinion.project_id == project.id)
        ).all()

        # THEN
        assert project.name == EXAMPLE_PROJECT_TEXT["cs"].name
        assert project.description == EXAMPLE_PROJECT_TEXT["cs"].description
        assert {o.position for o in opinions} == {e.position_cs for e in EXAMPLE_EXPERTS}

    def test_unknown_language_falls_back_to_english(self, session, owner):
        """An unexpected code seeds English rather than failing the activation."""
        # GIVEN
        service = ExampleProjectService(session)

        # WHEN
        project = service.seed_for(owner.id, language="de")
        opinions = session.exec(
            select(ExpertOpinion).where(ExpertOpinion.project_id == project.id)
        ).all()

        # THEN
        assert project.name == EXAMPLE_PROJECT_TEXT["en"].name
        assert {o.position for o in opinions} == {e.position_en for e in EXAMPLE_EXPERTS}


class TestSeedGuards:
    """When the service declines to seed."""

    def test_second_call_is_a_no_op(self, session, owner):
        """A retried activation must not give the account a second example."""
        # GIVEN
        service = ExampleProjectService(session)
        service.seed_for(owner.id)

        # WHEN
        again = service.seed_for(owner.id)
        projects = session.exec(select(Project).where(Project.admin_id == owner.id)).all()

        # THEN
        assert again is None
        assert len(projects) == 1

    def test_skips_when_the_demo_pool_is_missing(self, session_without_pool):
        """A database without the pool gets no example, not a foreign key error."""
        # GIVEN
        owner = _make_owner(session_without_pool, email="lonely@example.com")
        service = ExampleProjectService(session_without_pool)

        # WHEN
        project = service.seed_for(owner.id)
        projects = session_without_pool.exec(select(Project)).all()

        # THEN
        assert project is None
        assert projects == []

    def test_skips_when_the_demo_pool_is_partial(self, session_without_pool):
        """A half-applied migration must not seed a project on an incomplete pool.

        A count-based check ("are there at least 13 demo users?") and an identity
        check ("are these specific 13 accounts present?") agree once the pool is
        complete or empty, but they can diverge when it is partially applied -- this
        pins the guard to the identity check.
        """
        # GIVEN
        _insert_partial_demo_pool(session_without_pool, count=7)
        owner = _make_owner(session_without_pool, email="partial@example.com")
        service = ExampleProjectService(session_without_pool)

        # WHEN
        project = service.seed_for(owner.id)
        projects = session_without_pool.exec(select(Project)).all()

        # THEN
        assert project is None
        assert projects == []
