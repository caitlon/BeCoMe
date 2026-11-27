"""The state snapshot reads every table of the schema, token tables included.

Two guards back the "a refused request changed nothing" proof that the anonymous-access and
mass-assignment tests make with ``snapshot``. The table list must match the schema, so a new
model cannot go unwatched, and a write to a token table must change the snapshot, so a listed
table is really read.
"""

from datetime import timedelta
from typing import Any

import pytest
from sqlmodel import SQLModel

from api.db.models import EmailVerificationToken, PasswordResetToken, User
from api.db.utils import utc_now
from tests.integration.api.conftest import app_session
from tests.integration.api.state_snapshot import SNAPSHOT_TABLES, snapshot

# Obviously fake: 64 hex characters, the length the token_hash column demands.
FAKE_TOKEN_HASH = "ab" * 32  # pragma: allowlist secret


def _token(model: type[SQLModel], user_id: Any) -> SQLModel:
    """Build one unredeemed token row of ``model`` for a user.

    :param model: ``PasswordResetToken`` or ``EmailVerificationToken``.
    :param user_id: Id of the user the token belongs to.
    :return: The unsaved row, expiring in an hour.
    """
    fields: dict[str, Any] = {
        "user_id": user_id,
        "token_hash": FAKE_TOKEN_HASH,
        "expires_at": utc_now() + timedelta(hours=1),
    }
    if model is EmailVerificationToken:
        fields |= {
            "hashed_password": "x",  # pragma: allowlist secret
            "first_name": "Token",
            "last_name": "Holder",
        }
    return model(**fields)


def test_snapshot_covers_every_table_of_the_schema():
    """
    GIVEN the tables SQLModel knows once the models are imported
    WHEN they are compared with the tables the snapshot reads
    THEN the two sets are equal
    """
    # GIVEN
    schema = set(SQLModel.metadata.tables)

    # WHEN
    snapshotted = {str(model.__tablename__) for model in SNAPSHOT_TABLES}

    # THEN
    assert snapshotted == schema, (
        f"tables missing from the snapshot: {sorted(schema - snapshotted)}; "
        f"listed but not in the schema: {sorted(snapshotted - schema)}. "
        "Add a new model to SNAPSHOT_TABLES in tests/integration/api/state_snapshot.py."
    )


@pytest.mark.parametrize("model", [PasswordResetToken, EmailVerificationToken])
def test_snapshot_sees_a_write_to_a_token_table(client, model):
    """
    GIVEN a user and a snapshot of the database
    WHEN a token row is added for that user
    THEN a second snapshot differs from the first and holds the row under the model's name
    """
    # GIVEN
    with app_session(client) as session:
        user = User(email="holder@example.com", hashed_password="x", first_name="A", last_name="B")
        session.add(user)
        session.commit()
        user_id = user.id
        before = snapshot(session)

    # WHEN
    with app_session(client) as session:
        session.add(_token(model, user_id))
        session.commit()
        after = snapshot(session)

    # THEN
    assert before[model.__name__] == []
    assert after != before
    assert [row["token_hash"] for row in after[model.__name__]] == [FAKE_TOKEN_HASH]
