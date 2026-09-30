"""Render the account-verification email as an HTML document and a plain-text part.

The markup lives in ``layout.html`` and carries no words. Every human-readable string
is held here, so a language is added by writing one more :class:`VerificationCopy`
and listing it in ``COPIES``. Nothing in this module reads settings or touches the
network, so tests and previews can call :func:`render_verification_email` directly.
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
class VerificationCopy:
    """Static text of the verification email, in a single language.

    :param lang: Language code for the ``lang`` attribute of the document.
    :param subject: Subject line, also the document title.
    :param preheader: Hidden line some mail clients show after the subject.
    :param wordmark: Product name shown above the card.
    :param heading: Main heading of the message.
    :param body: Paragraph that says why the email was sent and what to do.
    :param button_label: Text of the confirmation button, and of the link label in the
        plain-text part.
    :param fallback: Line above the raw link, for clients that do not show the button.
    :param expiry: Sentence about the link's lifetime, with a ``{window}`` slot.
    :param not_you: Line for someone who did not register.
    :param footer: Closing line that says who sent the email and why.
    :param units: Unit words that fill the ``{window}`` slot, so a sentence is never half
        in another language.
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
    units: LifetimeUnits


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
    # One wording for the verification and the password-reset email alike. Minutes
    # keep one form for every count, as the reset email has always read.
    units=LifetimeUnits(
        hour=("hour", "hours", "hours"),
        minute=("minutes", "minutes", "minutes"),
    ),
)

_CS = VerificationCopy(
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
    units=LifetimeUnits(
        hour=("hodinu", "hodiny", "hodin"),
        minute=("minutu", "minuty", "minut"),
    ),
)

COPIES: dict[EmailLanguage, VerificationCopy] = {"en": _EN, "cs": _CS}


def format_lifetime(minutes: int, language: EmailLanguage) -> str:
    """Write a lifetime as a human-friendly window in a language.

    :param minutes: Lifetime in minutes.
    :param language: Language of the unit words.
    :return: ``"1 hour"`` / ``"N hours"`` for whole hours, else ``"N minutes"``, with
        the unit declined the way the language needs for the number.
    """
    units = COPIES[language].units
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


def render_verification_email(
    verify_url: str, expiry_minutes: int, language: EmailLanguage
) -> RenderedEmail:
    """Render the verification email in a language.

    Every value placed into the HTML is escaped, the link included. The plain-text
    part is not markup, so it carries the link as given.

    :param verify_url: Full frontend activation link.
    :param expiry_minutes: Lifetime of the link in minutes.
    :param language: Language the message is written in.
    :return: Subject, HTML document and plain-text alternative.
    """
    copy = COPIES[language]
    expiry = copy.expiry.format(window=format_lifetime(expiry_minutes, language))
    values = {
        **{name: value for name, value in asdict(copy).items() if isinstance(value, str)},
        "expiry": expiry,
        "verify_url": verify_url,
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
