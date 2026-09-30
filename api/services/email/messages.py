"""Render transactional emails as an HTML document and a plain-text part.

The page markup lives in ``layout.html`` and carries no words, and every message shares it.
The paragraphs under the links (the second link, the expiry and closing lines) are built in
this module with their own font, colours and rule, so restyling the layout means changing
``_NOTE_TYPE`` and ``_RULE`` here as well.

Every human-readable string is held here: a message is one table of :class:`EmailCopy` per
language, so a language is added by writing one more entry to each table, adding its value to
``EmailLanguage`` in ``api/services/email/base.py`` and to ``_SUPPORTED_EMAIL_LANGUAGES`` in
``api/dependencies.py``. Nothing in this module reads settings or touches the network, so
tests and previews can call :func:`render_verification_email`,
:func:`render_password_reset_email` and :func:`render_registration_notice_email` directly.
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
        Empty for a message whose link has no lifetime.
    :param not_you: Line for someone who did not ask for the email.
    :param footer: Closing line that says who sent the email and why.
    :param secondary_lead: Question that introduces a second link under the button, or empty
        when the message has none.
    :param secondary_link: Text of that second link. Its full stop, if any, stays out of the
        plain-text part.
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
    secondary_lead: str = ""
    secondary_link: str = ""


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

_PASSWORD_RESET_EN = EmailCopy(
    lang="en",
    subject="Reset your BeCoMe password",
    preheader="Use the link in this email to choose a new password.",
    wordmark="BeCoMe",
    heading="Reset your password",
    body=(
        "We received a request to reset the password for your BeCoMe account. Use the "
        "button below to choose a new one."
    ),
    button_label="Reset password",
    fallback="If the button doesn't work, copy and paste this link into your browser:",
    expiry="The link expires in {window}.",
    not_you=(
        "If you didn't ask for this, you can ignore this email. Your password stays the same."
    ),
    footer=(
        "You're receiving this email from BeCoMe at becomify.app because a password reset "
        "was requested for this address. It's an automatic message, so please don't reply."
    ),
)

_PASSWORD_RESET_CS = EmailCopy(
    lang="cs",
    subject="BeCoMe: obnovení hesla",
    preheader="Pomocí odkazu v e-mailu si zvolíte nové heslo.",
    wordmark="BeCoMe",
    heading="Obnovení hesla",
    body=(
        "Obdrželi jsme žádost o obnovení hesla k vašemu účtu BeCoMe. Tlačítkem níže si "
        "zvolíte nové heslo."
    ),
    button_label="Obnovit heslo",
    fallback="Pokud tlačítko nefunguje, zkopírujte tento odkaz do prohlížeče:",
    expiry="Odkaz platí {window}.",
    not_you=(
        "Pokud jste o obnovení nežádali, můžete tento e-mail ignorovat. Vaše heslo zůstává "
        "beze změny."
    ),
    footer=(
        "Tento e-mail vám posílá aplikace BeCoMe (becomify.app), protože někdo požádal o "
        "obnovení hesla pro tuto adresu. Jde o automatickou zprávu, na kterou prosím "
        "neodpovídejte."
    ),
)

PASSWORD_RESET_COPIES: dict[EmailLanguage, EmailCopy] = {
    "en": _PASSWORD_RESET_EN,
    "cs": _PASSWORD_RESET_CS,
}

_REGISTRATION_NOTICE_EN = EmailCopy(
    lang="en",
    subject="You already have a BeCoMe account",
    preheader="Someone tried to sign up with this address. Your account has not changed.",
    wordmark="BeCoMe",
    heading="You already have an account",
    body=(
        "Someone tried to sign up for BeCoMe with this email address, which already has an "
        "account. If it was you, sign in instead."
    ),
    button_label="Sign in",
    fallback="If the button doesn't work, copy and paste this link into your browser:",
    expiry="",
    not_you="If it wasn't you, you don't have to do anything. Your account has not changed.",
    footer=(
        "You're receiving this email from BeCoMe at becomify.app because someone entered "
        "this address in the sign-up form. It's an automatic message, so please don't reply."
    ),
    secondary_lead="Forgot your password?",
    secondary_link="Reset it.",
)

_REGISTRATION_NOTICE_CS = EmailCopy(
    lang="cs",
    subject="BeCoMe: účet s touto adresou už existuje",
    preheader="Někdo se pokusil zaregistrovat pod touto adresou. Váš účet zůstává beze změny.",
    wordmark="BeCoMe",
    heading="Účet už máte",
    body=(
        "Někdo se pokusil zaregistrovat do aplikace BeCoMe pod touto e-mailovou adresou, ke "
        "které už účet existuje. Pokud jste to byli vy, stačí se přihlásit."
    ),
    button_label="Přihlásit se",
    fallback="Pokud tlačítko nefunguje, zkopírujte tento odkaz do prohlížeče:",
    expiry="",
    not_you="Pokud jste to nebyli vy, nemusíte dělat nic. Váš účet zůstává beze změny.",
    footer=(
        "Tento e-mail vám posílá aplikace BeCoMe (becomify.app), protože někdo zadal tuto "
        "adresu do registračního formuláře. Jde o automatickou zprávu, na kterou prosím "
        "neodpovídejte."
    ),
    secondary_lead="Zapomněli jste heslo?",
    secondary_link="Obnovte si ho.",
)

REGISTRATION_NOTICE_COPIES: dict[EmailLanguage, EmailCopy] = {
    "en": _REGISTRATION_NOTICE_EN,
    "cs": _REGISTRATION_NOTICE_CS,
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


_FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
_NOTE_TYPE = f"font-family:{_FONT};font-size:14px;line-height:20px;color:#595959;"
_RULE = "padding:20px 0 0 0;border-top:1px solid #E6E6E6;"
# Copy fields that reach the layout through the paragraphs built here, not one placeholder each.
_ROW_FIELDS = {"expiry", "not_you", "secondary_lead", "secondary_link"}


def _secondary_row(copy: EmailCopy, url: str) -> str:
    """Build the paragraph with a second link, for a message that has one.

    :param copy: Text of the message in the language.
    :param url: Full link the second link opens.
    :return: An escaped ``<p>`` element.
    """
    return (
        f'<p class="muted" style="margin:0 0 28px 0;{_NOTE_TYPE}">'
        f"{escape(copy.secondary_lead, quote=True)} "
        f'<a href="{escape(url, quote=True)}" class="fallback-link" '
        'style="color:#1A1A1A;text-decoration:underline;">'
        f"{escape(copy.secondary_link, quote=True)}</a></p>"
    )


def _note_rows(notes: list[str]) -> list[str]:
    """Build the closing paragraphs under the links, the first one under a rule.

    The last paragraph carries no bottom margin, so the card keeps the same padding whether
    a message has one closing paragraph or two.

    :param notes: Sentences in the order they read.
    :return: Escaped ``<p>`` elements.
    """
    rows = []
    for index, note in enumerate(notes):
        first, last = index == 0, index == len(notes) - 1
        css_class = "muted rule" if first else "muted"
        margin = "0" if last else "0 0 8px 0"
        rule = _RULE if first else ""
        rows.append(
            f'<p class="{css_class}" style="margin:{margin};{rule}{_NOTE_TYPE}">'
            f"{escape(note, quote=True)}</p>"
        )
    return rows


def _render(
    copy: EmailCopy,
    action_url: str,
    language: EmailLanguage,
    *,
    expiry_minutes: int | None = None,
    secondary_url: str | None = None,
) -> RenderedEmail:
    """Fill the layout and the plain-text part with one copy and its links.

    Every value placed into the HTML is escaped, the links included. The plain-text
    part is not markup, so it carries the links as given. The paragraphs under the links are
    built here, so a message without a second link or a lifetime leaves no empty row.

    :param copy: Text of the message in the language.
    :param action_url: Full frontend link the button opens.
    :param language: Language the message is written in.
    :param expiry_minutes: Lifetime of the link in minutes, or ``None`` for a message
        that has no expiry sentence.
    :param secondary_url: Full link of the second link, or ``None`` for a message without one.
    :return: Subject, HTML document and plain-text alternative.
    """
    expiry = (
        copy.expiry.format(window=format_lifetime(expiry_minutes, language))
        if expiry_minutes is not None
        else ""
    )
    notes = [note for note in (expiry, copy.not_you) if note]
    rows = [] if secondary_url is None else [_secondary_row(copy, secondary_url)]
    rows += _note_rows(notes)
    html = _LAYOUT.substitute(
        {
            **{
                name: escape(value, quote=True)
                for name, value in asdict(copy).items()
                if name not in _ROW_FIELDS
            },
            "action_url": escape(action_url, quote=True),
            "rows": "\n".join(rows),
        }
    )
    paragraphs = [copy.wordmark, copy.heading, copy.body, f"{copy.button_label}:\n{action_url}"]
    if secondary_url is not None:
        label = f"{copy.secondary_lead} {copy.secondary_link.removesuffix('.')}"
        paragraphs.append(f"{label}:\n{secondary_url}")
    if notes:
        paragraphs.append(" ".join(notes))
    paragraphs.append(copy.footer)
    return RenderedEmail(subject=copy.subject, html=html, text="\n\n".join(paragraphs))


def render_verification_email(
    verify_url: str, expiry_minutes: int, language: EmailLanguage
) -> RenderedEmail:
    """Render the verification email in a language.

    :param verify_url: Full frontend activation link.
    :param expiry_minutes: Lifetime of the link in minutes.
    :param language: Language the message is written in.
    :return: Subject, HTML document and plain-text alternative.
    """
    return _render(
        VERIFICATION_COPIES[language], verify_url, language, expiry_minutes=expiry_minutes
    )


def render_password_reset_email(
    reset_url: str, expiry_minutes: int, language: EmailLanguage
) -> RenderedEmail:
    """Render the password-reset email in a language.

    :param reset_url: Full frontend reset link.
    :param expiry_minutes: Lifetime of the link in minutes.
    :param language: Language the message is written in.
    :return: Subject, HTML document and plain-text alternative.
    """
    return _render(
        PASSWORD_RESET_COPIES[language], reset_url, language, expiry_minutes=expiry_minutes
    )


def render_registration_notice_email(
    login_url: str, reset_url: str, language: EmailLanguage
) -> RenderedEmail:
    """Render the notice sent when someone signs up with an address that has an account.

    :param login_url: Full frontend sign-in link, which the button opens.
    :param reset_url: Full frontend password-reset link, offered under the button.
    :param language: Language the message is written in.
    :return: Subject, HTML document and plain-text alternative.
    """
    return _render(
        REGISTRATION_NOTICE_COPIES[language], login_url, language, secondary_url=reset_url
    )
