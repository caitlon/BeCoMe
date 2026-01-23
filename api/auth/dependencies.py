"""Authentication dependencies for FastAPI.

This module provides authentication-related dependencies following
the Dependency Inversion Principle (DIP). The Session dependency is
injected, and UserService is created with this injected dependency.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session

from api.auth.jwt import TokenError, TokenPayload, decode_access_token, decode_token
from api.db.models import User
from api.db.session import get_session
from api.services.user_service import UserService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[Session, Depends(get_session)],
) -> User:
    """Extract and validate current user from JWT token.

    Session is injected via DI, UserService is created with
    the injected session (following DIP).

    :param token: JWT access token from Authorization header
    :param session: Injected database session
    :return: Authenticated User
    :raises HTTPException: 401 if token invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        user_id = decode_access_token(token)
    except TokenError as e:
        raise credentials_exception from e

    user_service = UserService(session)
    user = user_service.get_by_id(user_id)
    if user is None:
        raise credentials_exception
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_token_payload(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> TokenPayload:
    """Extract and validate token payload from JWT.

    Used for logout to get JTI without loading user from DB.

    :param token: JWT access token from Authorization header
    :return: TokenPayload with jti, exp, and user_id
    :raises HTTPException: 401 if token invalid
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        return decode_token(token, "access")
    except TokenError as e:
        raise credentials_exception from e
