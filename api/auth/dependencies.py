"""Authentication dependencies for FastAPI.

This module provides authentication-related dependencies following
the Dependency Inversion Principle (DIP). The Session dependency is
injected, and UserService is created with this injected dependency.
"""

from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session

from api.auth.cookies import ACCESS_COOKIE
from api.auth.jwt import TokenError, TokenPayload, decode_access_token, decode_token
from api.auth.revocation_store import RevocationStore, get_revocation_store
from api.config import get_settings
from api.db.models import User
from api.db.session import get_session
from api.logging_context import set_user_id
from api.services.user_cache import CachedUserData, UserCacheStore, get_user_cache
from api.services.user_service import UserService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def _get_access_token(
    cookie_token: Annotated[str | None, Cookie(alias=ACCESS_COOKIE)] = None,
    bearer_token: Annotated[str | None, Depends(oauth2_scheme)] = None,
) -> str:
    """Return the access token from the session cookie, else the Bearer header.

    The cookie is the primary transport for the browser SPA; the Authorization header
    stays as a fallback for programmatic clients and the test suite.

    :param cookie_token: Access token from the HttpOnly session cookie.
    :param bearer_token: Access token from the Authorization header.
    :return: The access token to validate.
    :raises HTTPException: 401 when neither transport carries a token.
    """
    token = cookie_token or bearer_token
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


async def get_current_user(
    token: Annotated[str, Depends(_get_access_token)],
    session: Annotated[Session, Depends(get_session)],
    store: Annotated[RevocationStore, Depends(get_revocation_store)],
    cache: Annotated[UserCacheStore, Depends(get_user_cache)],
) -> User:
    """Return the authenticated user, served from cache when possible.

    On a cache hit a transient ``User`` is rebuilt from the cached snapshot and
    the database is not touched. On a miss the user is loaded from the DB and the
    snapshot is cached. Revocation checks run *before* the cache, so token
    invalidation is unaffected.

    :param token: JWT access token.
    :param session: Injected database session (used only on a miss).
    :param store: Revocation store consulted during token validation.
    :param cache: User profile cache.
    :return: Authenticated ``User`` (transient on a hit, session-bound on a miss).
    :raises HTTPException: 401 if the token is invalid or the user is not found.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        user_id = decode_access_token(token, store)
    except TokenError as e:
        raise credentials_exception from e

    cached = cache.get(user_id)
    if cached is not None:
        user = cached.to_user()
    else:
        user_service = UserService(session)
        loaded = await run_in_threadpool(user_service.get_by_id, user_id)
        if loaded is None:
            raise credentials_exception
        cache.set(CachedUserData.from_user(loaded), get_settings().user_cache_ttl_seconds)
        user = loaded

    set_user_id(str(user.id))
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_user_fresh(
    token: Annotated[str, Depends(_get_access_token)],
    session: Annotated[Session, Depends(get_session)],
    store: Annotated[RevocationStore, Depends(get_revocation_store)],
) -> User:
    """Return the authenticated user always loaded fresh from the DB (no cache).

    Used by mutating endpoints: they need a session-bound ``User`` to modify and
    the real ``hashed_password``, neither of which the cache provides.

    :param token: JWT access token.
    :param session: Injected database session.
    :param store: Revocation store consulted during token validation.
    :return: Session-bound authenticated ``User``.
    :raises HTTPException: 401 if the token is invalid or the user is not found.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        user_id = decode_access_token(token, store)
    except TokenError as e:
        raise credentials_exception from e

    user_service = UserService(session)
    user = await run_in_threadpool(user_service.get_by_id, user_id)
    if user is None:
        raise credentials_exception
    set_user_id(str(user.id))
    return user


CurrentUserFresh = Annotated[User, Depends(get_current_user_fresh)]


def get_current_token_payload(
    token: Annotated[str, Depends(_get_access_token)],
    store: Annotated[RevocationStore, Depends(get_revocation_store)],
) -> TokenPayload:
    """Extract and validate token payload from JWT.

    Used for logout to get JTI without loading user from DB.

    :param token: JWT access token from Authorization header
    :param store: Revocation store consulted during token validation
    :return: TokenPayload with jti, exp, and user_id
    :raises HTTPException: 401 if token invalid
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        return decode_token(token, "access", store)
    except TokenError as e:
        raise credentials_exception from e
