"""Render transactional emails as an HTML document and a plain-text part.

The markup lives in ``layout.html`` and carries no words, and every message shares it.
Every human-readable string is held here: a message is one table of :class:`EmailCopy`
per language, so a language is added by writing one more entry to each table, adding its
value to ``EmailLanguage`` in ``api/services/email/base.py`` and to
``_SUPPORTED_EMAIL_LANGUAGES`` in ``api/dependencies.py``. Nothing in this module reads
settings or touches the network, so tests and previews can call
:func:`render_verification_email` directly.
"""

from dataclasses import asdict, dataclass
from html import escape
from pathlib import Path
from string import Template

from api.services.email.base import EmailLanguage

_MINUTES_PER_HOUR = 60


@dataclass(frozen=True, slots=True)
class LifetimeUnits:
    """Unit words for writing a lifetime, each in the three forms a number picks.

    :param hour: Forms of "hour" for 1, for 2 to 4, and for 5 and more.
    :param minute: Forms of "minute" for 1, for 2 to 4, and for 5 and more.
    """

    hour: tuple[str, str, str]
    minute: tuple[str, str, str]


@dataclass(frozen=True, slots=True)
class EmailCopy:
    """Static text of one email, in a single language.

    :param lang: Language code for the ``lang`` attribute of the document.
    :param subject: Subject line, also the document title.
    :param preheader: Hidden line some mail clients show after the subject.
    :param wordmark: Product name shown above the card.
    :param heading: Main heading of the message.
    :param body: Paragraph that says why the email was sent and what to do.
    :param button_label: Text of the button, and of the link label in the plain-text part.
    :param fallback: Line above the raw link, for clients that do not show the button.
    :param expiry: Sentence about the link's lifetime, with a ``{window}`` slot that
        :func:`format_lifetime` fills, so a sentence is never half in another language.
    :param not_you: Line for someone who did not ask for the email.
    :param footer: Closing line that says who sent the email and why.
    """

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

_VERIFICATION_EN = EmailCopy(
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

_VERIFICATION_CS = EmailCopy(
    lang="cs",
    subject="BeCoMe: potvrďte svůj e-mail",
    preheader="Otevřete odkaz a zadejte své heslo. Tím účet aktivujete.",
    wordmark="BeCoMe",
    heading="Potvrďte svůj e-mail",
    body=(
        "Děkujeme za registraci v aplikaci BeCoMe. Pro aktivaci účtu potvrďte tuto "
        "e-mailovou adresu a na další stránce zadejte své heslo."
    ),
    button_label="Potvrdit e-mail",
    fallback="Pokud tlačítko nefunguje, zkopírujte tento odkaz do prohlížeče:",
    expiry="Odkaz platí {window}.",
    not_you="Pokud jste se v aplikaci BeCoMe neregistrovali, můžete tento e-mail ignorovat.",
    footer=(
        "Tento e-mail vám posílá aplikace BeCoMe (becomify.app), protože se vaší "
        "e-mailovou adresou někdo zaregistroval. Jde o automatickou zprávu, na kterou "
        "prosím neodpovídejte."
    ),
)

VERIFICATION_COPIES: dict[EmailLanguage, EmailCopy] = {
    "en": _VERIFICATION_EN,
    "cs": _VERIFICATION_CS,
}

# One wording for every email. English has no separate form for 2 to 4, so the second and
# third entries repeat.
_LIFETIME_UNITS: dict[EmailLanguage, LifetimeUnits] = {
    "en": LifetimeUnits(
        hour=("hour", "hours", "hours"),
        minute=("minute", "minutes", "minutes"),
    ),
    "cs": LifetimeUnits(
        hour=("hodinu", "hodiny", "hodin"),
        minute=("minutu", "minuty", "minut"),
    ),
}


def format_lifetime(minutes: int, language: EmailLanguage) -> str:
    """Write a lifetime as a human-friendly window in a language.

    :param minutes: Lifetime in minutes.
    :param language: Language of the unit words.
    :return: ``"1 hour"`` / ``"N hours"`` for whole hours, else ``"N minutes"``, with
        the unit declined the way the language needs for the number.
    """
    units = _LIFETIME_UNITS[language]
    if minutes % _MINUTES_PER_HOUR == 0:
        count, forms = minutes // _MINUTES_PER_HOUR, units.hour
    else:
        count, forms = minutes, units.minute
    if count == 1:
        word = forms[0]
    elif 2 <= count <= 4:
        word = forms[1]
    else:
        word = forms[2]
    return f"{count} {word}"


def _render(
    copy: EmailCopy, action_url: str, expiry_minutes: int, language: EmailLanguage
) -> RenderedEmail:
    """Fill the layout and the plain-text part with one copy and one link.

    Every value placed into the HTML is escaped, the link included. The plain-text
    part is not markup, so it carries the link as given.

    :param copy: Text of the message in the language.
    :param action_url: Full frontend link the button opens.
    :param expiry_minutes: Lifetime of the link in minutes.
    :param language: Language the message is written in.
    :return: Subject, HTML document and plain-text alternative.
    """
    expiry = copy.expiry.format(window=format_lifetime(expiry_minutes, language))
    values = {**asdict(copy), "expiry": expiry, "action_url": action_url}
    html = _LAYOUT.substitute({key: escape(value, quote=True) for key, value in values.items()})
    text = "\n\n".join(
        (
            copy.wordmark,
            copy.heading,
            copy.body,
            f"{copy.button_label}:\n{action_url}",
            f"{expiry} {copy.not_you}",
            copy.footer,
        )
    )
    return RenderedEmail(subject=copy.subject, html=html, text=text)


def render_verification_email(
    verify_url: str, expiry_minutes: int, language: EmailLanguage
) -> RenderedEmail:
    """Render the verification email in a language.

    :param verify_url: Full frontend activation link.
    :param expiry_minutes: Lifetime of the link in minutes.
    :param language: Language the message is written in.
    :return: Subject, HTML document and plain-text alternative.
    """
    return _render(VERIFICATION_COPIES[language], verify_url, expiry_minutes, language)
