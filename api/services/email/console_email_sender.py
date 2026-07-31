"""Development email sender that logs messages instead of sending them."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from api.auth.logging import hash_email
from api.services.email.base import EmailSender

if TYPE_CHECKING:
    from api.config import Settings

logger = logging.getLogger("api.service.email")

_TOKEN_PREFIX_LEN = 8


def _mask_token(url: str) -> str:
    """Mask the token value in a URL's ``token`` query parameter.

    Keeps a few leading characters so two links stay distinguishable in the log
    without exposing the full single-use token. Returns the URL unchanged when
    it carries no ``token`` parameter.

    :param url: Full link, possibly carrying a ``token`` query parameter.
    :return: The URL with the token value masked.

    >>> _mask_token("https://app/reset-password?token=abcdefghijklmnop")
    'https://app/reset-password?token=abcdefgh...'
    """
    parts = urlparse(url)
    params = parse_qs(parts.query)
    raw = params.get("token", [""])[0]
    if not raw:
        return url
    params["token"] = [f"{raw[:_TOKEN_PREFIX_LEN]}..." if len(raw) > _TOKEN_PREFIX_LEN else "..."]
    return urlunparse(parts._replace(query=urlencode(params, doseq=True)))


class ConsoleEmailSender(EmailSender):
    """Log transactional links instead of sending an email.

    Used in development, CI, and tests: every flow works offline and each link is
    read straight from the application log or stdout. The deployed profiles reject
    an unconfigured email provider at startup (``Settings._validate_deploy_invariants``),
    so this sender cannot be selected there -- a link and its token only ever
    reach a developer-visible log. Recipients are tagged with the same
    :func:`hash_email` digest the security log uses, never the raw address.

    :param settings: Application settings (kept for a uniform sender signature).
    """

    def __init__(self, settings: Settings) -> None:
        """Store settings for signature parity with real senders."""
        self._settings = settings

    async def send_password_reset(self, *, to_email: str, reset_url: str) -> None:
        """Log the reset link; perform no network call.

        The log record masks the single-use token, so a rotating file or a log drain
        never captures a redeemable link. The dev flow still needs a usable one, so the
        full link is written straight to stdout instead of through the ``api`` logger
        tree -- no handler, present or future, can ship it off the machine.

        :param to_email: Recipient email address.
        :param reset_url: Full frontend reset link (carries the raw token).
        """
        email_hash = hash_email(to_email)
        logger.info(
            "Password reset link (console sender) for %s: %s",
            email_hash,
            _mask_token(reset_url),
            extra={"event": "password_reset_email", "email_hash": email_hash},
        )
        # Deliberately not a log record -- see the docstring.
        print(f"[console email] password reset link for {email_hash}: {reset_url}")

    async def send_email_verification(self, *, to_email: str, verify_url: str) -> None:
        """Log the verification link; perform no network call.

        Same rationale as :meth:`send_password_reset`: the record masks the
        single-use token, and the full link goes to stdout so the local
        end-to-end flow can copy it out without a real mail provider.

        :param to_email: Recipient email address.
        :param verify_url: Full frontend activation link (carries the raw token).
        """
        email_hash = hash_email(to_email)
        logger.info(
            "Email verification link (console sender) for %s: %s",
            email_hash,
            _mask_token(verify_url),
            extra={"event": "verification_email", "email_hash": email_hash},
        )
        # Deliberately not a log record -- see the docstring on send_password_reset.
        print(f"[console email] verification link for {email_hash}: {verify_url}")

    async def send_registration_attempt_notice(
        self, *, to_email: str, login_url: str, reset_url: str
    ) -> None:
        """Log the registration-attempt notice; perform no network call.

        Masks either link's ``token`` query parameter the same way as
        :meth:`send_password_reset`, whether or not one is actually present, and
        prints both full links to stdout for the local dev flow.

        :param to_email: Recipient email address (the existing account's address).
        :param login_url: Full frontend sign-in link.
        :param reset_url: Full frontend password-reset link.
        """
        email_hash = hash_email(to_email)
        logger.info(
            "Registration attempt notice (console sender) for %s: login=%s reset=%s",
            email_hash,
            _mask_token(login_url),
            _mask_token(reset_url),
            extra={"event": "registration_attempt_notice_email", "email_hash": email_hash},
        )
        # Deliberately not a log record -- see the docstring on send_password_reset.
        print(
            f"[console email] registration attempt notice for {email_hash}: "
            f"login={login_url} reset={reset_url}"
        )
