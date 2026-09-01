"""Defaults of the two flags that carry the example-project feature.

Both must default to false: every project created through the API is real work, and
every account created through registration is a person. Only the seeding service and
the migration ever set them.
"""

from uuid import uuid4

from api.db.models import Project, User


class TestIsExampleDefault:
    """Project.is_example."""

    def test_defaults_to_false(self):
        """A project created the ordinary way is not an example."""
        # GIVEN/WHEN
        project = Project(name="Real work", admin_id=uuid4())

        # THEN
        assert project.is_example is False

    def test_can_be_set(self):
        """The seeding service marks its project explicitly."""
        # GIVEN/WHEN
        project = Project(name="Example", admin_id=uuid4(), is_example=True)

        # THEN
        assert project.is_example is True


class TestIsDemoDefault:
    """User.is_demo."""

    def test_defaults_to_false(self):
        """A registered account is never a demo account."""
        # GIVEN/WHEN
        user = User(
            email="person@example.com",
            hashed_password="x",
            first_name="Real",
            last_name="Person",
        )

        # THEN
        assert user.is_demo is False

    def test_can_be_set(self):
        """The migration marks the seeded pool explicitly."""
        # GIVEN/WHEN
        user = User(
            email="demo@example.invalid",
            hashed_password="x",
            first_name="Demo",
            last_name="Expert",
            is_demo=True,
        )

        # THEN
        assert user.is_demo is True
