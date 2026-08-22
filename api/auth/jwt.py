"""JWT token creation and decoding with refresh token support."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from jwt import InvalidTokenError

from api.auth.revocation_store import RevocationStore, RevocationStoreError
from api.config import get_settings

logger = logging.getLogger("api.security")

ALGORITHM = "HS256"

# Refusals that are ordinary traffic, not a signal: an access token expires every 15
# minutes, so every active session hits this, and so does every stale browser tab.
# Logged at DEBUG so the refusals that do mean something -- a revoked token, an
# unreachable store -- stay visible in a stream filtered to WARNING.
_ROUTINE_REJECTIONS = frozenset({"invalid_or_expired", "invalid_user_id"})


class TokenError(Exception):
    """Raised when token validation fails."""


def _reject(reason: str, message: str, **fields: object) -> TokenError:
    """Log a refused token and build the error to raise.

    The token string never reaches the record -- only why it was refused and the
    opaque identifiers needed to correlate the refusal with the session it came from.

    :param reason: Machine-readable cause, e.g. ``jti_revoked``.
    :param message: Message carried by the raised :class:`TokenError`.
    :param fields: Extra context to attach to the record.
    :return: The error the caller should raise.
    """
    level = logging.DEBUG if reason in _ROUTINE_REJECTIONS else logging.WARNING
    logger.log(
        level,
        "Token rejected",
        extra={"event": "token_rejected", "reason": reason, **fields},
    )
    return TokenError(message)


@dataclass(frozen=True)
class TokenPair:
    """Access and refresh token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105 -- OAuth2 scheme name, not a credential
    expires_in: int = 0  # Access token lifetime in seconds
    jti: str = ""  # Shared jti of this access/refresh pair
    sid: str = ""  # Session id shared across the whole rotation family


@dataclass(frozen=True)
class TokenPayload:
    """Decoded token payload."""

    user_id: UUID
    jti: str
    token_type: str
    exp: datetime
    sid: str = ""  # Session id, empty for legacy tokens minted before sessions


def create_access_token(user_id: UUID, sid: str | None = None, jti: str | None = None) -> str:
    """Create a JWT access token for a user.

    :param user_id: User's UUID
    :param sid: Session id shared with the paired refresh token (generated if omitted)
    :param jti: Optional JWT ID (generated if not provided)
    :return: Encoded JWT token string
    """
    settings = get_settings()
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": now,
        "jti": jti or uuid4().hex,
        "sid": sid or uuid4().hex,
        "type": "access",
    }
    encoded: str = jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)
    return encoded


def create_refresh_token(user_id: UUID, sid: str | None = None) -> tuple[str, str]:
    """Create a JWT refresh token for a user.

    :param user_id: User's UUID
    :param sid: Session id for the rotation family (generated if omitted)
    :return: Tuple of (encoded token, jti)
    """
    settings = get_settings()
    now = datetime.now(UTC)
    expire = now + timedelta(days=settings.refresh_token_expire_days)
    jti = uuid4().hex
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": now,
        "jti": jti,
        "sid": sid or uuid4().hex,
        "type": "refresh",
    }
    encoded: str = jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)
    return encoded, jti


def create_token_pair(user_id: UUID, sid: str | None = None) -> TokenPair:
    """Create both access and refresh tokens for a user.

    Both tokens share one ``sid`` (the rotation family) and one ``jti``. Pass an
    existing ``sid`` to keep a rotated pair in the same family; omit it at login to
    start a fresh family.

    :param user_id: User's UUID
    :param sid: Session id to continue, or ``None`` to start a new family
    :return: TokenPair with both tokens plus the shared jti and sid
    """
    settings = get_settings()
    session_id = sid or uuid4().hex
    refresh_token, jti = create_refresh_token(user_id, session_id)
    access_token = create_access_token(user_id, session_id, jti)
    logger.debug(
        "Token pair issued",
        extra={
            "event": "token_pair_issued",
            "user_id": str(user_id),
            "sid": session_id,
            "jti": jti,
            "expires_in": settings.access_token_expire_minutes * 60,
            "continued": sid is not None,
        },
    )
    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
        jti=jti,
        sid=session_id,
    )


def decode_token(token: str, expected_type: str, store: RevocationStore) -> TokenPayload:
    """Decode and validate a JWT token.

    :param token: JWT token string
    :param expected_type: Expected token type ('access' or 'refresh')
    :param store: Revocation store consulted for the token's JTI
    :return: TokenPayload with decoded data
    :raises TokenError: If token is invalid, expired, or revoked
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[ALGORITHM],
            options={
                "verify_exp": True,
                "verify_iat": True,
                "require": ["exp", "iat"],
            },
        )

        token_type: str | None = payload.get("type")
        if token_type != expected_type:
            raise _reject(
                "type_mismatch",
                f"Invalid token type: expected {expected_type}",
                expected_type=expected_type,
            )

        jti: str | None = payload.get("jti")
        if not jti:
            raise _reject("missing_jti", "Missing token ID", expected_type=expected_type)

        # Check revocation store (fail-closed: a store error becomes a 401)
        try:
            revoked = store.is_jti_revoked(jti)
        except RevocationStoreError as e:
            raise _reject(
                "store_unavailable", "Revocation store unavailable", op="is_jti_revoked"
            ) from e
        if revoked:
            raise _reject("jti_revoked", "Token has been revoked", jti=jti)

        # Reject any token whose session (sid) was revoked. Refresh-token reuse
        # revokes the whole family, so a stolen token cannot outlive detection.
        sid: str | None = payload.get("sid")
        if sid:
            try:
                session_revoked = store.is_session_revoked(sid)
            except RevocationStoreError as e:
                raise _reject(
                    "store_unavailable", "Revocation store unavailable", op="is_session_revoked"
                ) from e
            if session_revoked:
                raise _reject("session_revoked", "Token has been revoked", jti=jti, sid=sid)

        user_id_str: str | None = payload.get("sub")
        if not user_id_str:
            raise _reject("missing_sub", "Missing user ID in token", expected_type=expected_type)
        user_id = UUID(user_id_str)

        # Reject tokens issued before the user's valid_after cutoff (M1): a password
        # change or reset invalidates every token minted earlier.
        try:
            valid_after = store.get_user_valid_after(user_id)
        except RevocationStoreError as e:
            raise _reject(
                "store_unavailable", "Revocation store unavailable", op="get_user_valid_after"
            ) from e
        if valid_after is not None and datetime.fromtimestamp(payload["iat"], tz=UTC) < valid_after:
            raise _reject(
                "issued_before_valid_after",
                "Token has been revoked",
                jti=jti,
                user_id=str(user_id),
            )

        # exp is guaranteed by PyJWT with require=["exp"]
        exp_datetime = datetime.fromtimestamp(payload["exp"], tz=UTC)

        return TokenPayload(
            user_id=user_id,
            jti=jti,
            token_type=token_type,
            exp=exp_datetime,
            sid=sid or "",
        )
    except InvalidTokenError as e:
        raise _reject(
            "invalid_or_expired", "Invalid or expired token", expected_type=expected_type
        ) from e
    except ValueError as e:
        raise _reject(
            "invalid_user_id", "Invalid user ID in token", expected_type=expected_type
        ) from e


def decode_access_token(token: str, store: RevocationStore) -> UUID:
    """Decode and validate a JWT access token.

    :param token: JWT token string
    :param store: Revocation store consulted for the token's JTI
    :return: User UUID from token
    :raises TokenError: If token is invalid, expired, or revoked
    """
    payload = decode_token(token, "access", store)
    return payload.user_id


def decode_refresh_token(token: str, store: RevocationStore) -> TokenPayload:
    """Decode and validate a JWT refresh token.

    :param token: JWT token string
    :param store: Revocation store consulted for the token's JTI
    :return: TokenPayload with user_id, jti, and exp
    :raises TokenError: If token is invalid, expired, or revoked
    """
    return decode_token(token, "refresh", store)


def session_id_from_access_token(token: str) -> str | None:
    """Return the session id an access token carries, without consulting the store.

    Written for the CSRF middleware, which runs before routing and only needs to know
    *which session* a request would authenticate as, so it can derive that session's
    expected token. The signature is still verified -- otherwise a caller could name any
    session -- but expiry, revocation, and the per-user cutoff are not, because those are
    the authentication layer's job and checking them here would put three Redis round
    trips in front of every mutating request. A token that fails any of them is refused a
    few milliseconds later by :func:`decode_token`; letting it reach that refusal with the
    CSRF check already applied is strictly the stricter order.

    :param token: Raw access token from the session cookie.
    :return: The session id, or None when the token is unreadable, is not an access
        token, or predates sessions (no ``sid`` claim).
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[ALGORITHM],
            options={"verify_exp": False, "require": ["exp", "iat"]},
        )
    except InvalidTokenError:
        return None
    if payload.get("type") != "access":
        return None
    sid = payload.get("sid")
    return sid if isinstance(sid, str) and sid else None


def refresh_token_ttl_seconds() -> int:
    """Return the refresh-token lifetime in seconds.

    Used as the TTL for revocation and session records so they outlive every token
    they must invalidate but do not linger in the store forever.

    :return: Refresh-token lifetime in seconds.
    """
    return get_settings().refresh_token_expire_days * 86400


def revoke_token(jti: str, store: RevocationStore) -> None:
    """Revoke a token by recording its JTI in the revocation store.

    Revokes for the full refresh token lifetime so that any refresh token
    sharing this JTI cannot be used after revocation, even if revocation was
    initiated using an access token.

    :param jti: JWT ID to revoke
    :param store: Revocation store to record the JTI in
    """
    store.revoke_jti(jti, refresh_token_ttl_seconds())
    logger.debug("Token revoked", extra={"event": "token_revoked", "jti": jti})
