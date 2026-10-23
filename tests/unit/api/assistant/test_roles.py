"""Tests for the role a failure carries from the code that talks to a server to the log."""

from api.assistant.roles import tag_role, tagged_role


class TestTagRole:
    """The first tag written on an exception is the one that stays."""

    def test_an_untagged_exception_has_no_role(self):
        """
        GIVEN an exception nothing tagged
        WHEN its role is read
        THEN there is none
        """
        assert tagged_role(RuntimeError("x")) is None

    def test_tagging_twice_keeps_the_first_role(self):
        """
        GIVEN an exception tagged by the code closest to the server
        WHEN code further out tags it again
        THEN the first role is still the one it carries
        """
        error = RuntimeError("x")

        tag_role(error, "answer")
        tag_role(error, "app_api")

        assert tagged_role(error) == "answer"
