"""Render the account-verification email as an HTML document and a plain-text part.

The markup lives in ``layout.html`` and carries no words. Every human-readable string
is held here, so a language is added by writing one more :class:`VerificationCopy`.
Nothing in this module reads settings or touches the network, so tests and previews
can call :func:`render_verification_email` directly.
"""

from dataclasses import dataclass
from html import escape
from pathlib import Path
from string import Template


@dataclass(frozen=True, slots=True)
class VerificationCopy:
    """Static text of the verification email, in a single language."""

    lang: str
    subject: str
    preheader: str
    wordmark: str
    heading: str
    body: str
    button_label: str
    fallback: str
    expiry: str
    not_you: str
    footer: str


@dataclass(frozen=True, slots=True)
class RenderedEmail:
    """A finished message: the subject and both bodies.

    :param subject: Subject line.
    :param html: Complete HTML document.
    :param text: Plain-text alternative carrying the same message.
    """

    subject: str
    html: str
    text: str


_LAYOUT_PATH = Path(__file__).with_name("layout.html")
_LAYOUT = Template(_LAYOUT_PATH.read_text(encoding="utf-8"))

_EN = VerificationCopy(
    lang="en",
    subject="Confirm your BeCoMe email",
    preheader="Open the link and enter your password to activate your account.",
    wordmark="BeCoMe",
    heading="Confirm your email",
    body=(
        "Thanks for creating a BeCoMe account. To activate it, confirm this email address "
        "and enter your password on the next page."
    ),
    button_label="Confirm email",
    fallback="If the button doesn't work, copy and paste this link into your browser:",
    expiry="The link expires in {window}.",
    not_you="If you didn't create a BeCoMe account, you can ignore this email.",
    footer=(
        "You're receiving this email from BeCoMe at becomify.app because your email "
        "address was used to create an account. It's an automatic message, so please "
        "don't reply."
    ),
)


def render_verification_email(verify_url: str, expiry_window: str) -> RenderedEmail:
    """Render the verification email in English.

    Every value placed into the HTML is escaped, the link included. The plain-text
    part is not markup, so it carries the link as given.

    :param verify_url: Full frontend activation link.
    :param expiry_window: Lifetime of the link as text, e.g. ``"24 hours"``.
    :return: Subject, HTML document and plain-text alternative.
    """
    copy = _EN
    expiry = copy.expiry.format(window=expiry_window)
    values = {
        "lang": copy.lang,
        "subject": copy.subject,
        "preheader": copy.preheader,
        "wordmark": copy.wordmark,
        "heading": copy.heading,
        "body": copy.body,
        "button_label": copy.button_label,
        "verify_url": verify_url,
        "fallback": copy.fallback,
        "expiry": expiry,
        "not_you": copy.not_you,
        "footer": copy.footer,
    }
    html = _LAYOUT.substitute({key: escape(value, quote=True) for key, value in values.items()})
    text = "\n\n".join(
        (
            copy.wordmark,
            copy.heading,
            copy.body,
            f"{copy.button_label}:\n{verify_url}",
            f"{expiry} {copy.not_you}",
            copy.footer,
        )
    )
    return RenderedEmail(subject=copy.subject, html=html, text=text)
