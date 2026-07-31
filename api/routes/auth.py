"""Authentication routes: register, login, logout, refresh, profile.

Exception handling follows OCP: all exceptions are handled
by centralized middleware, routes focus on business logic only.
"""

import logging
from collections.abc import Awaitable
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from starlette.concurrency import run_in_threadpool

from api.auth.cookies import (
    REFRESH_COOKIE,
    clear_auth_cookies,
    cookies_secure,
    new_csrf_token,
    set_auth_cookies,
)
from api.auth.dependencies import CurrentUser, get_current_token_payload
from api.auth.email_throttle import (
    EmailSendThrottle,
    get_reset_email_throttle,
    get_verification_email_throttle,
)
from api.auth.jwt import (
    TokenError,
    TokenPair,
    TokenPayload,
    create_token_pair,
    decode_refresh_token,
    refresh_token_ttl_seconds,
    revoke_token,
)
from api.auth.logging import (
    log_email_verified,
    log_login_blocked_unverified,
    log_login_success,
    log_password_reset_completed,
    log_password_reset_requested,
    log_registration_attempt,
    log_verification_email_requested,
    log_verification_password_mismatch,
)
from api.auth.login_throttle import (
    LoginThrottle,
    get_activation_throttle,
    get_login_throttle,
)
from api.auth.password import hash_password
from api.auth.revocation_store import RevocationStore, get_revocation_store
from api.config import get_settings
from api.dependencies import (
    get_email_address_policy,
    get_email_service,
    get_email_verification_service,
    get_password_reset_service,
    get_registration_service,
    get_user_service,
)
from api.exceptions import (
    EmailNotVerifiedError,
    InvalidCredentialsError,
    LoginThrottledError,
    VerificationPasswordMismatchError,
)
from api.middleware.rate_limit import LIMIT_AUTH_ENDPOINTS, LIMIT_PWD_RESET, limiter
from api.schemas.auth import (
    ForgotPasswordRequest,
    RefreshTokenRequest,
    RegisterRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
    VerifyEmailRequest,
)
from api.services.email.base import EmailSender
from api.services.email.exceptions import EmailSendError
from api.services.email_policy import EmailAddressPolicy
from api.services.email_verification_service import EmailVerificationService
from api.services.password_reset_service import PasswordResetService
from api.services.registration_service import RegistrationService
from api.services.user_service import UserService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

logger = logging.getLogger("api.route.auth")

# One acknowledgement for every registration submission. Returning the same body for a
# free address, a taken-but-unverified one, and a taken-and-verified one is what keeps
# the endpoint from reporting whether an address already has an account.
_REGISTRATION_ACCEPTED = "Check your inbox to finish signing up."

# Also fixed regardless of whether anything was actually emailed.
_RESEND_ACCEPTED = "If that address still needs confirming, a new link is on its way."

_VERIFICATION_COMPLETE = "Your email address is confirmed. You can sign in now."


def _set_session_cookies(response: Response, token_pair: TokenPair, request: Request) -> None:
    """Attach the access, refresh, and CSRF cookies for a freshly issued token pair.

    :param response: The response to set cookies on.
    :param token_pair: The newly minted access/refresh pair.
    :param request: The incoming request, used to decide the cookie Secure flag.
    """
    set_auth_cookies(
        response,
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        csrf_token=new_csrf_token(),
        access_ttl=token_pair.expires_in,
        refresh_ttl=refresh_token_ttl_seconds(),
        secure=cookies_secure(request),
    )


def _may_mail(throttle: EmailSendThrottle, email: str, *, created: bool) -> bool:
    """Decide whether registration may mail this address, spending a slot either way.

    The branch that created the account is never denied: it fires at most once per
    address, so it can flood nothing, and charging it to a budget a stranger can drain
    with five unauthenticated resend requests would let anyone pre-empt a signup that
    has not happened yet. It still *spends* a slot, though. A send that spent nothing
    would leave the address's budget clean, so a second, back-to-back submission would
    mail again for a free address while a taken one had already gone quiet -- and the
    awaited round trip to the mail provider is exactly the difference the uniform 202
    exists to hide.

    :param throttle: Per-address cap on the emails this flow can trigger.
    :param email: Address the email would go to.
    :param created: Whether this submission is the one that created the account.
    :return: Whether to send.
    """
    if created:
        throttle.record(email)
        return True
    return throttle.allow(email)


async def _send_quietly(send: Awaitable[None], event: str) -> None:
    """Await a transactional send and swallow a provider failure.

    The endpoints that mail an unauthenticated address answer identically whether or
    not an email went out. Letting a provider error through would undo that: the caller
    would learn that a send was attempted, and therefore that the address has an
    account.

    :param send: The pending send coroutine.
    :param event: Structured log event name to record on failure.
    """
    try:
        await send
    except EmailSendError:
        logger.warning("Transactional email send failed", extra={"event": event})


@router.post(
    "/register",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Register a new user and send an activation link",
)
@limiter.limit(LIMIT_AUTH_ENDPOINTS)
async def register(
    request: Request,
    data: RegisterRequest,
    registration: Annotated[RegistrationService, Depends(get_registration_service)],
    verification: Annotated[EmailVerificationService, Depends(get_email_verification_service)],
    email_service: Annotated[EmailSender, Depends(get_email_service)],
    policy: Annotated[EmailAddressPolicy, Depends(get_email_address_policy)],
    throttle: Annotated[EmailSendThrottle, Depends(get_verification_email_throttle)],
) -> dict[str, str]:
    """Accept a registration and email whoever owns the address.

    Always answers 202 with the same body, so the response never reveals whether the
    address already has an account. What happens behind it is decided by
    :class:`~api.services.registration_service.RegistrationService`; a free or
    still-unverified address gets an activation link, an already-verified one gets a
    notice that someone tried to sign up with it.

    The address policy runs first, before anything touches the database. Both of its
    rejections depend only on the domain string, so returning a 400 for them leaks
    nothing about account existence.

    :param request: FastAPI request (for rate limiting and logging)
    :param data: Registration data (email, password, name)
    :param registration: Registration policy service
    :param verification: Email verification service (mints the activation link)
    :param email_service: Email sender
    :param policy: Registration address policy (disposable domains, DNS)
    :param throttle: Per-address cap on the emails registration can trigger
    :return: A fixed acknowledgement message
    :raises DisposableEmailDomainError: If the domain is a known disposable provider
    :raises UnresolvableEmailDomainError: If the domain cannot receive mail
    """
    await policy.check(data.email)

    # Blocking work (bcrypt plus the account write), so it runs in a worker thread
    # rather than freezing every other request on this worker for a few hundred ms.
    # The session is handed to that thread and back sequentially, never shared.
    result = await run_in_threadpool(
        registration.register,
        email=data.email,
        password=data.password,
        first_name=data.first_name,
        last_name=data.last_name,
    )

    # Every branch is capped per address (a hashed key), so posting a victim's address
    # here from rotating IPs cannot flood their inbox past the per-IP limiter. The
    # response is unchanged whether or not a send happens; see _may_mail for why the
    # creating branch spends from the budget without being gated by it.
    # Do not flatten the two conditions into one: a pending account whose send is
    # suppressed would then fall into the elif and be mailed a notice instead, which is
    # both the wrong message and a second charge against the same budget.
    if result.user is not None:
        if _may_mail(throttle, data.email, created=result.created):
            verify_url = verification.create_verification_url(result.user, result.credentials)
            await _send_quietly(
                email_service.send_email_verification(to_email=data.email, verify_url=verify_url),
                "verification_email_failed",
            )
    elif throttle.allow(data.email):
        # A static reset link, never a minted token: an unauthenticated registration
        # attempt must not be able to mail anyone a working password-reset link.
        frontend = get_settings().frontend_base_url
        await _send_quietly(
            email_service.send_registration_attempt_notice(
                to_email=data.email,
                login_url=f"{frontend}/login",
                reset_url=f"{frontend}/forgot-password",
            ),
            "registration_notice_email_failed",
        )

    log_registration_attempt(data.email, request)
    return {"detail": _REGISTRATION_ACCEPTED}


@router.post("/login", summary="Login and get access + refresh tokens")
@limiter.limit(LIMIT_AUTH_ENDPOINTS)
def login(
    request: Request,
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    service: Annotated[UserService, Depends(get_user_service)],
    store: Annotated[RevocationStore, Depends(get_revocation_store)],
    throttle: Annotated[LoginThrottle, Depends(get_login_throttle)],
) -> TokenResponse:
    """Authenticate user and return JWT tokens.

    Uses OAuth2 password flow: username field contains email.
    Returns both access token (short-lived) and refresh token (long-lived).
    A fresh session (rotation family) is registered so later refreshes can be
    rotated atomically and a reused refresh token can be contained.
    Failed attempts are counted per account and the account is locked for a cooldown
    once the threshold is passed, so guesses cannot simply be spread across many IPs.
    An account whose address is not verified yet is refused with 403.
    InvalidCredentialsError is handled by centralized exception middleware.
    Rate limited to prevent brute-force password attacks.

    :param request: FastAPI request (for rate limiting)
    :param form_data: OAuth2 form with username (email) and password
    :param service: User service
    :param store: Revocation store (records the new session's current token)
    :param throttle: Per-account login throttle (lockout after repeated failures)
    :return: JWT access and refresh tokens
    :raises EmailNotVerifiedError: If the account has not confirmed its address
    """
    if throttle.is_locked(form_data.username):
        raise LoginThrottledError
    try:
        user = service.authenticate(form_data.username, form_data.password)
    except InvalidCredentialsError:
        throttle.record_failure(form_data.username)
        raise
    # After the password check, never before: refusing an unverified account up front
    # would answer differently for an address that has an account and one that does
    # not, turning the endpoint into an enumeration oracle. A correct password on an
    # unverified account is not a failed attempt, so nothing is recorded -- and nothing
    # is reset either, since the login did not succeed.
    if user.email_verified_at is None:
        log_login_blocked_unverified(user.id, request)
        raise EmailNotVerifiedError
    throttle.reset(form_data.username)
    token_pair = create_token_pair(user.id)
    store.start_session(token_pair.sid, token_pair.jti, refresh_token_ttl_seconds())
    _set_session_cookies(response, token_pair, request)

    log_login_success(user.id, user.email, request)

    return TokenResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        expires_in=token_pair.expires_in,
    )


@router.post(
    "/verify-email",
    status_code=status.HTTP_200_OK,
    summary="Confirm an email address using an activation token",
)
@limiter.limit(LIMIT_PWD_RESET)
def verify_email(
    request: Request,
    data: VerifyEmailRequest,
    service: Annotated[EmailVerificationService, Depends(get_email_verification_service)],
    throttle: Annotated[LoginThrottle, Depends(get_activation_throttle)],
    login_throttle: Annotated[LoginThrottle, Depends(get_login_throttle)],
) -> dict[str, str]:
    """Redeem an activation token and mark the account's address verified.

    The emailed link points at the frontend, which posts the token here, so a mail
    client prefetching the link with a GET cannot burn a single-use token. Redemption
    takes the token *and* the password of the submission that minted it, checked
    against the token rather than against the stored account: a link that reaches an
    inbox its submitter does not control is then dead in both hands, since the
    recipient cannot supply the password and the submitter never sees the link.
    Redeeming writes what the token carries, so the account opens on the terms of the
    submission being redeemed, not of whoever submitted the address most recently.

    InvalidVerificationTokenError and VerificationTokenExpiredError are handled by
    centralized middleware and both map to 400 with the same opaque message, so an
    unknown token cannot be told apart from a spent or expired one. A wrong password
    answers 403 instead, on purpose: the caller already holds a live link, and telling
    someone who mistyped that their link is broken would send them off for another one.

    That leaves a guessing oracle, capped by its own per-account lockout -- distinct
    from the one POST /login uses. A run of failed logins, which anyone who merely
    knows the address can produce without ever holding a link, never touches this
    counter, so it can never deny someone their own activation; only a caller who
    already holds a live token can move it at all. A mismatch here still spends from
    the login counter too, so the combined guessing budget across the two endpoints is
    unchanged -- only each endpoint's own lockout decision is now independent. Rate
    limited.

    :param request: FastAPI request (for rate limiting and logging)
    :param data: The raw token from the activation link and its password
    :param service: Email verification service
    :param throttle: Per-account activation-guess throttle (lockout after repeated
        mismatches on this endpoint)
    :param login_throttle: Per-account login throttle; a mismatch spends from it too so
        the combined guessing bound between the two endpoints does not grow, but it is
        never consulted here
    :return: A fixed confirmation message
    :raises InvalidVerificationTokenError: If the token is unknown, spent, or its
        account is already verified
    :raises VerificationTokenExpiredError: If the token has expired
    :raises LoginThrottledError: If the account is locked after repeated activation
        mismatches
    :raises VerificationPasswordMismatchError: If the password is not the one the
        token carries
    """
    # The token is resolved first, so a caller holding a bad one never reaches the
    # throttle and every bad-token answer stays identical. Resolving also refuses an
    # account that is already verified, which is what keeps this endpoint from being
    # able to lock a live account out of its own login.
    pending = service.resolve_pending_activation(data.token)
    if throttle.is_locked(pending.email):
        raise LoginThrottledError
    try:
        user = service.activate(pending, data.password)
    except VerificationPasswordMismatchError:
        throttle.record_failure(pending.email)
        login_throttle.record_failure(pending.email)
        log_verification_password_mismatch(pending.user_id, request)
        raise
    throttle.reset(pending.email)

    log_email_verified(user.id, request)
    return {"detail": _VERIFICATION_COMPLETE}


@router.post(
    "/resend-verification",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request a fresh activation link",
)
@limiter.limit(LIMIT_PWD_RESET)
async def resend_verification(
    request: Request,
    data: ResendVerificationRequest,
    service: Annotated[EmailVerificationService, Depends(get_email_verification_service)],
    email_service: Annotated[EmailSender, Depends(get_email_service)],
    throttle: Annotated[EmailSendThrottle, Depends(get_verification_email_throttle)],
) -> dict[str, str]:
    """Email a fresh activation link, if the address has one to send.

    Always returns the same 202 whether the address is unknown, unverified, or already
    verified, so the endpoint cannot be used to enumerate accounts. Shares the
    registration flow's per-address throttle: both land in the same inbox, so an
    attacker must not get a second allowance by switching endpoints. Rate limited.

    The password makes this a repeat registration minus the names, and the link it
    mails carries that submission like any other: redeeming it means restating the
    password, and the names come from the account, which is all a resend can know. An
    address-only resend would instead hand out a link anybody receiving the mail could
    follow, which would reopen the takeover the whole flow closes.

    :param request: FastAPI request (for rate limiting and logging)
    :param data: Address to send the activation link to, and the password it opens on
    :param service: Email verification service
    :param email_service: Email sender
    :param throttle: Per-address cap on the emails the registration flow can trigger
    :return: A fixed acknowledgement message
    """
    # Hashed before the lookup and unconditionally, so the branch with nothing to send
    # spends the same bcrypt as the one that mints a link. In a worker thread because
    # bcrypt blocks for 100-300 ms and this route runs on the event loop.
    hashed_password = await run_in_threadpool(hash_password, data.password)

    # Look first, spend after. A request naming an address with nothing to resend must
    # not consume that address's budget: it takes no authentication to name someone
    # else's address here, and a spent budget silently suppresses the mail a genuine
    # signup depends on.
    pending = service.find_unverified_account(data.email)
    if pending is not None and throttle.allow(data.email):
        verify_url = service.create_resend_url(pending, hashed_password)
        await _send_quietly(
            email_service.send_email_verification(to_email=data.email, verify_url=verify_url),
            "verification_email_failed",
        )

    log_verification_email_requested(data.email, request)
    return {"detail": _RESEND_ACCEPTED}


@router.post("/refresh", summary="Refresh access token")
@limiter.limit(LIMIT_AUTH_ENDPOINTS)
def refresh_token(
    request: Request,
    response: Response,
    store: Annotated[RevocationStore, Depends(get_revocation_store)],
    data: RefreshTokenRequest | None = None,
    refresh_cookie: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> TokenResponse:
    """Exchange a refresh token for a new access + refresh pair (rotation).

    The session's current refresh token is atomically consumed and a fresh pair is
    issued in the same family. Presenting an already-rotated (reused) refresh token
    is treated as theft: the whole family is revoked so neither the stolen token nor
    the legitimate one keeps working, and the caller must log in again. Rate limited.

    :param request: FastAPI request (for rate limiting)
    :param data: Refresh token request
    :param store: Revocation store (rotates the session, contains reuse)
    :return: New access and refresh tokens
    :raises HTTPException: If the refresh token is invalid, expired, revoked, or reused
    """
    # The SPA sends the refresh token via the HttpOnly cookie (which it cannot read into
    # a body); programmatic clients still post it in the request body.
    refresh = refresh_cookie or (data.refresh_token if data else None)
    if refresh is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_refresh_token(refresh, store)
    except TokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    ttl = refresh_token_ttl_seconds()
    if payload.sid:
        # Atomically consume the family's current refresh token and issue the next
        # pair in the same session. If the presented token is not the current one it
        # is a reused (already-rotated) token: revoke the whole family so a stolen
        # token cannot keep rotating, and return the same opaque 401.
        token_pair = create_token_pair(payload.user_id, sid=payload.sid)
        if not store.rotate_session(payload.sid, payload.jti, token_pair.jti, ttl):
            store.revoke_session(payload.sid, ttl)
            logger.warning(
                "Refresh token reuse detected; session revoked",
                extra={"event": "refresh_reuse_detected"},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        _set_session_cookies(response, token_pair, request)
        return TokenResponse(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            expires_in=token_pair.expires_in,
        )

    # Legacy refresh token minted before sessions existed: revoke it and migrate to
    # the session model by starting a fresh family.
    revoke_token(payload.jti, store)
    token_pair = create_token_pair(payload.user_id)
    store.start_session(token_pair.sid, token_pair.jti, ttl)
    _set_session_cookies(response, token_pair, request)
    return TokenResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        expires_in=token_pair.expires_in,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout and revoke current token",
)
def logout(
    response: Response,
    token_payload: Annotated[TokenPayload, Depends(get_current_token_payload)],
    store: Annotated[RevocationStore, Depends(get_revocation_store)],
) -> None:
    """Revoke the current session and clear the auth cookies.

    Blacklists the token's JTI and revokes its whole session, so every access and
    refresh token in the family stops working -- even a still-valid access token
    issued before an earlier rotation.

    :param response: Response used to clear the auth cookies.
    :param token_payload: Current token payload from JWT
    :param store: Revocation store
    """
    revoke_token(token_payload.jti, store)
    if token_payload.sid:
        store.revoke_session(token_payload.sid, refresh_token_ttl_seconds())
    clear_auth_cookies(response)


@router.post(
    "/forgot-password",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request a password reset email",
)
@limiter.limit(LIMIT_PWD_RESET)
async def forgot_password(
    request: Request,
    data: ForgotPasswordRequest,
    service: Annotated[PasswordResetService, Depends(get_password_reset_service)],
    email_service: Annotated[EmailSender, Depends(get_email_service)],
    throttle: Annotated[EmailSendThrottle, Depends(get_reset_email_throttle)],
) -> dict[str, str]:
    """Start the password reset flow for the given email.

    Always returns the same 202 response whether or not the email is registered,
    so the endpoint cannot reveal which addresses have accounts. When a user
    exists a reset link is emailed; send failures are swallowed for the same
    reason. Rate limited to slow abuse.

    :param request: FastAPI request (for rate limiting and logging)
    :param data: Email to send the reset link to
    :param service: Password reset service
    :param email_service: Email sender
    :return: A fixed acknowledgement message
    """
    # Cap reset emails per address (a hashed key) so a known inbox cannot be flooded by
    # rotating IPs past the per-IP limiter. The response is unchanged whether or not a
    # send happens, preserving the anti-enumeration guarantee.
    if throttle.allow(data.email):
        reset_url = service.create_reset_token(data.email)
        if reset_url is not None:
            await _send_quietly(
                email_service.send_password_reset(to_email=data.email, reset_url=reset_url),
                "password_reset_email_failed",
            )

    log_password_reset_requested(data.email, request)
    return {"detail": "If that email is registered, a reset link has been sent."}


@router.post(
    "/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reset password using a token",
)
@limiter.limit(LIMIT_PWD_RESET)
def reset_password(
    request: Request,
    data: ResetPasswordRequest,
    service: Annotated[PasswordResetService, Depends(get_password_reset_service)],
    store: Annotated[RevocationStore, Depends(get_revocation_store)],
    throttle: Annotated[LoginThrottle, Depends(get_login_throttle)],
) -> None:
    """Set a new password using a valid reset token.

    InvalidResetTokenError and ResetTokenExpiredError are handled by centralized
    middleware and both map to 400 with the same opaque message. Rate limited.
    Every token issued before the reset is invalidated (M1).

    :param request: FastAPI request (for rate limiting and logging)
    :param data: Reset token and new password
    :param service: Password reset service
    :param store: Revocation store (invalidates sessions issued before the reset)
    :param throttle: Per-account login throttle, cleared once the reset completes
    """
    # Order matters: resolve the token, close the session window, then write. Recording
    # the cutoff first means a store fault surfaces as a 503 with the password unchanged
    # and the token unspent, rather than committing a new password while every session
    # issued before the reset stays valid. Presenting a valid token already proves
    # takeover capability, so revoking before the write concedes nothing.
    user = service.resolve_valid_token(data.token)
    store.set_user_valid_after(user.id, datetime.now(UTC))
    service.reset_password(data.token, data.new_password)

    # A login lockout is writable by anyone who merely knows the address, and it would
    # otherwise survive its owner proving control of the mailbox and choosing a new
    # password: an attacker who tripped it can just resume the same failed guesses once
    # the window reopens and keep the account locked out indefinitely.
    throttle.reset(user.email)

    log_password_reset_completed(user.id, request)


@router.get("/me", summary="Get current user profile")
def get_me(current_user: CurrentUser) -> UserResponse:
    """Return the authenticated user's profile.

    :param current_user: User from JWT token
    :return: User profile data
    """
    return UserResponse.from_user(current_user)
