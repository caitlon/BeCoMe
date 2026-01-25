"""Tests for database schema verification (indexes, constraints)."""

from sqlalchemy import inspect


class TestDatabaseSchema:
    """Tests to verify database schema correctness.

    Table names in SQLModel follow convention: lowercase with underscores.
    - User -> users
    - Project -> projects
    - ProjectMember -> project_members
    - ExpertOpinion -> expert_opinions
    - CalculationResult -> calculation_results
    """

    def test_user_email_index_exists(self, test_engine):
        """
        GIVEN the database schema
        WHEN inspected
        THEN users.email has an index
        """
        # GIVEN/WHEN
        inspector = inspect(test_engine)
        indexes = inspector.get_indexes("users")
        index_columns = [idx["column_names"] for idx in indexes]

        # THEN
        assert any("email" in cols for cols in index_columns)

    def test_unique_index_on_user_email(self, test_engine):
        """
        GIVEN the database schema
        WHEN inspected
        THEN users.email has unique index (unique constraint via index)
        """
        # GIVEN/WHEN
        inspector = inspect(test_engine)
        indexes = inspector.get_indexes("users")

        # THEN - find unique index on email
        email_indexes = [idx for idx in indexes if "email" in idx["column_names"]]
        assert any(idx.get("unique") for idx in email_indexes)

    def test_foreign_key_indexes_exist_on_project_member(self, test_engine):
        """
        GIVEN the database schema
        WHEN inspected
        THEN project_members FK columns have indexes
        """
        # GIVEN/WHEN
        inspector = inspect(test_engine)
        indexes = inspector.get_indexes("project_members")
        index_columns = [col for idx in indexes for col in idx["column_names"]]

        # THEN
        assert "project_id" in index_columns
        assert "user_id" in index_columns

    def test_unique_constraint_on_project_member(self, test_engine):
        """
        GIVEN the database schema
        WHEN inspected
        THEN project_members has unique constraint on (project_id, user_id)
        """
        # GIVEN/WHEN
        inspector = inspect(test_engine)
        unique_constraints = inspector.get_unique_constraints("project_members")

        # THEN
        has_composite_unique = any(
            "project_id" in uc["column_names"] and "user_id" in uc["column_names"]
            for uc in unique_constraints
        )
        assert has_composite_unique

    def test_unique_constraint_on_expert_opinion(self, test_engine):
        """
        GIVEN the database schema
        WHEN inspected
        THEN expert_opinions has unique constraint on (project_id, user_id)
        """
        # GIVEN/WHEN
        inspector = inspect(test_engine)
        unique_constraints = inspector.get_unique_constraints("expert_opinions")

        # THEN
        has_composite_unique = any(
            "project_id" in uc["column_names"] and "user_id" in uc["column_names"]
            for uc in unique_constraints
        )
        assert has_composite_unique

    def test_calculation_result_project_id_unique(self, test_engine):
        """
        GIVEN the database schema
        WHEN inspected
        THEN calculation_results.project_id has unique index (one result per project)
        """
        # GIVEN/WHEN
        inspector = inspect(test_engine)
        indexes = inspector.get_indexes("calculation_results")

        # THEN - find unique index on project_id
        project_indexes = [idx for idx in indexes if "project_id" in idx["column_names"]]
        assert any(idx.get("unique") for idx in project_indexes)
