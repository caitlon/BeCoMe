"""Tests for the rendered transactional emails and their shared layout file.

The layout is a data file with placeholders and no words of its own, so a language is
added by swapping the strings alone. The renderers are pure functions, so every test
here calls them directly with no settings and no network.
"""

import html as html_lib
import re
from dataclasses import asdict, fields, replace
from html.parser import HTMLParser
from importlib.resources import files
from typing import get_args

import pytest

from api.services.email import messages
from api.services.email.base import EmailLanguage
from api.services.email.messages import (
    PASSWORD_RESET_COPIES,
    REGISTRATION_NOTICE_COPIES,
    VERIFICATION_COPIES,
    EmailCopy,
    RenderedEmail,
    format_lifetime,
    render_password_reset_email,
    render_registration_notice_email,
    render_verification_email,
)

_URL = "https://app.example/verify-email?token=abc"
_HOSTILE_URL = 'https://app.example/verify?a=1&b="x"<y'
_HOSTILE_URL_ESCAPED = "https://app.example/verify?a=1&amp;b=&quot;x&quot;&lt;y"
_DAY = 24 * 60

_SUBJECT = "Confirm your BeCoMe email"
_PREHEADER = "Open the link and enter your password to activate your account."
_HEADING = "Confirm your email"
_BODY = (
    "Thanks for creating a BeCoMe account. To activate it, confirm this email address "
    "and enter your password on the next page."
)
_BUTTON = "Confirm email"
_FALLBACK = "If the button doesn't work, copy and paste this link into your browser:"
_NOT_YOU = "If you didn't create a BeCoMe account, you can ignore this email."
_FOOTER = (
    "You're receiving this email from BeCoMe at becomify.app because your email address "
    "was used to create an account. It's an automatic message, so please don't reply."
)

_CS_SUBJECT = "BeCoMe: potvrďte svůj e-mail"
_CS_PREHEADER = "Otevřete odkaz a zadejte své heslo. Tím účet aktivujete."
_CS_HEADING = "Potvrďte svůj e-mail"
_CS_BODY = (
    "Děkujeme za registraci v aplikaci BeCoMe. Pro aktivaci účtu potvrďte tuto "
    "e-mailovou adresu a na další stránce zadejte své heslo."
)
_CS_BUTTON = "Potvrdit e-mail"
_CS_FALLBACK = "Pokud tlačítko nefunguje, zkopírujte tento odkaz do prohlížeče:"
_CS_NOT_YOU = "Pokud jste se v aplikaci BeCoMe neregistrovali, můžete tento e-mail ignorovat."
_CS_FOOTER = (
    "Tento e-mail vám posílá aplikace BeCoMe (becomify.app), protože se vaší e-mailovou "
    "adresou někdo zaregistroval. Jde o automatickou zprávu, na kterou prosím neodpovídejte."
)

_RESET_URL = "https://app.example/reset-password?token=abc"

# The reset copy as it must read, per language. The expiry sentence is checked apart,
# since it carries the lifetime.
_RESET = {
    "en": {
        "subject": "Reset your BeCoMe password",
        "preheader": "Use the link in this email to choose a new password.",
        "heading": "Reset your password",
        "body": (
            "We received a request to reset the password for your BeCoMe account. "
            "Use the button below to choose a new one."
        ),
        "button_label": "Reset password",
        "fallback": "If the button doesn't work, copy and paste this link into your browser:",
        "not_you": (
            "If you didn't ask for this, you can ignore this email. Your password stays the same."
        ),
        "footer": (
            "You're receiving this email from BeCoMe at becomify.app because a password "
            "reset was requested for this address. It's an automatic message, so please "
            "don't reply."
        ),
    },
    "cs": {
        "subject": "BeCoMe: obnovení hesla",
        "preheader": "Pomocí odkazu v e-mailu si zvolíte nové heslo.",
        "heading": "Obnovení hesla",
        "body": (
            "Obdrželi jsme žádost o obnovení hesla k vašemu účtu BeCoMe. Tlačítkem níže "
            "si zvolíte nové heslo."
        ),
        "button_label": "Obnovit heslo",
        "fallback": "Pokud tlačítko nefunguje, zkopírujte tento odkaz do prohlížeče:",
        "not_you": (
            "Pokud jste o obnovení nežádali, můžete tento e-mail ignorovat. Vaše heslo "
            "zůstává beze změny."
        ),
        "footer": (
            "Tento e-mail vám posílá aplikace BeCoMe (becomify.app), protože někdo požádal "
            "o obnovení hesla pro tuto adresu. Jde o automatickou zprávu, na kterou prosím "
            "neodpovídejte."
        ),
    },
}
_RESET_EXPIRY = {"en": "The link expires in {window}.", "cs": "Odkaz platí {window}."}

# Fields that land in the head of the document or are rebuilt before they are placed.
_HEAD_FIELDS = {"lang", "subject", "preheader", "expiry"}
# Fields the renderer sets as paragraphs under the link, not through a placeholder each.
_ROW_FIELDS = {"expiry", "not_you", "secondary_lead", "secondary_link"}
# Placeholders the renderer fills besides the copy.
_CALLER_PLACEHOLDERS = {"action_url", "rows"}


def _render(url: str = _URL, minutes: int = _DAY, language: EmailLanguage = "en") -> RenderedEmail:
    """Render the verification email for a link, a lifetime in minutes and a language."""
    return render_verification_email(url, minutes, language)


def _layout() -> str:
    """Read the layout file as shipped."""
    return files("api.services.email").joinpath("layout.html").read_text(encoding="utf-8")


class _TextNodes(HTMLParser):
    """Collect the visible text of a document, leaving out the style block."""

    def __init__(self) -> None:
        super().__init__()
        self.nodes: list[str] = []
        self._in_style = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._in_style = tag == "style"

    def handle_endtag(self, tag: str) -> None:
        if tag == "style":
            self._in_style = False

    def handle_data(self, data: str) -> None:
        if not self._in_style and data.strip():
            self.nodes.append(data.strip())


class TestRenderedSubject:
    """The subject line is part of the result."""

    def test_subject_is_the_confirmation_subject(self):
        """
        GIVEN a verification link
        WHEN the email is rendered in English
        THEN the subject is the fixed English subject line
        """
        # WHEN
        rendered = _render()

        # THEN
        assert rendered.subject == _SUBJECT

    def test_czech_subject(self):
        """
        GIVEN a verification link
        WHEN the email is rendered in Czech
        THEN the subject is the Czech subject line
        """
        # WHEN
        rendered = _render(language="cs")

        # THEN
        assert rendered.subject == _CS_SUBJECT

    @pytest.mark.parametrize("language", ["en", "cs"])
    def test_title_element_carries_the_subject(self, language: EmailLanguage):
        """
        GIVEN a rendered email
        WHEN its html is read
        THEN the document title equals the subject
        """
        # GIVEN
        rendered = _render(language=language)

        # WHEN
        title = f"<title>{html_lib.escape(rendered.subject, quote=True)}</title>"

        # THEN
        assert title in rendered.html


class TestRenderedHtml:
    """The html part is one complete, designed document."""

    def test_is_a_complete_document_in_english(self):
        """
        GIVEN a verification link
        WHEN the email is rendered
        THEN the html is a full document declaring English
        """
        # WHEN
        rendered = _render()

        # THEN
        assert rendered.html.lstrip().startswith("<!DOCTYPE html>")
        assert '<html lang="en"' in rendered.html
        assert rendered.html.rstrip().endswith("</html>")

    def test_carries_the_preheader_and_footer(self):
        """
        GIVEN a rendered email
        WHEN its html is read
        THEN the preheader and the footer sentence are present
        """
        # WHEN
        rendered = _render()

        # THEN
        assert html_lib.escape(_PREHEADER, quote=True) in rendered.html
        assert html_lib.escape(_FOOTER, quote=True) in rendered.html

    def test_heading_sits_inside_an_h1(self):
        """
        GIVEN a rendered email
        WHEN its html is read
        THEN the heading text is the content of an h1 element
        """
        # WHEN
        html = _render().html

        # THEN
        assert re.search(rf"<h1[^>]*>\s*{_HEADING}\s*</h1>", html)

    def test_button_label_sits_inside_the_link_to_the_url(self):
        """
        GIVEN a rendered email
        WHEN its html is read
        THEN the button label is the text of the anchor whose href is the URL
        """
        # GIVEN
        pattern = rf'<a href="{re.escape(_URL)}"[^>]*>\s*{_BUTTON}\s*</a>'

        # WHEN
        html = _render().html

        # THEN
        assert re.search(pattern, html)

    def test_states_the_lifetime_in_the_html(self):
        """
        GIVEN a lifetime of one hour
        WHEN the email is rendered
        THEN the html says so and never mentions another window
        """
        # WHEN
        rendered = _render(minutes=60)

        # THEN
        assert "The link expires in 1 hour." in rendered.html
        assert "24 hours" not in rendered.html

    @pytest.mark.parametrize("language", ["en", "cs"])
    def test_url_is_escaped_everywhere_it_appears(self, language: EmailLanguage):
        """
        GIVEN a URL holding an ampersand, a double quote and an angle bracket
        WHEN the email is rendered
        THEN the html carries the escaped form in both hrefs and the visible text, and the
            raw form nowhere
        """
        # WHEN
        rendered = _render(url=_HOSTILE_URL, language=language)

        # THEN
        assert _HOSTILE_URL not in rendered.html
        assert rendered.html.count(_HOSTILE_URL_ESCAPED) == 3
        assert rendered.html.count(f'href="{_HOSTILE_URL_ESCAPED}"') == 2
        assert f">{_HOSTILE_URL_ESCAPED}</a>" in rendered.html

    @pytest.mark.parametrize("language", ["en", "cs"])
    def test_no_placeholder_survives(self, language: EmailLanguage):
        """
        GIVEN a rendered email
        WHEN its html and text are read
        THEN neither holds a dollar sign left over from the layout
        """
        # WHEN
        rendered = _render(language=language)

        # THEN
        assert "$" not in rendered.html
        assert "$" not in rendered.text

    def test_the_button_cell_pads_for_outlook(self):
        """
        GIVEN a rendered email
        WHEN the cell that holds the button is read
        THEN it carries mso-padding-alt, since Outlook ignores padding on the link
        """
        # WHEN
        cell = re.search(r'<td class="button-cell"[^>]*>', _render().html)

        # THEN
        assert cell is not None
        assert "mso-padding-alt:14px 28px" in cell.group(0)


class TestEveryPartOfTheCopyReachesTheMessage:
    """A copy field, or a placeholder, that nothing carries into the message fails here."""

    def test_every_layout_placeholder_is_a_copy_field_or_the_link(self):
        """
        GIVEN the layout file
        WHEN its placeholders are listed
        THEN they are exactly the text fields of the copy that the layout places itself, plus
            the link and the rows, so a line deleted from the layout, or a field the layout
            never uses, is caught
        """
        # GIVEN
        expected = {f.name for f in fields(EmailCopy)} - _ROW_FIELDS | _CALLER_PLACEHOLDERS

        # WHEN
        placeholders = set(re.findall(r"\$([a-z_]+)", _layout()))

        # THEN
        assert placeholders == expected

    @pytest.mark.parametrize("language", ["en", "cs"])
    def test_every_copy_field_is_a_visible_piece_of_the_html(self, language: EmailLanguage):
        """
        GIVEN a rendered email
        WHEN the text nodes of its html are collected
        THEN each copy field is among them or inside one, the wordmark as a node of its own
        """
        # GIVEN
        copy = VERIFICATION_COPIES[language]
        text_fields = {
            name: value
            for name, value in asdict(copy).items()
            if value and name not in _HEAD_FIELDS
        }

        # WHEN
        parser = _TextNodes()
        parser.feed(_render(language=language).html)
        nodes = [html_lib.unescape(node) for node in parser.nodes]

        # THEN
        assert text_fields
        for name, value in text_fields.items():
            assert any(value in node for node in nodes), name
        assert copy.wordmark in nodes

    @pytest.mark.parametrize("language", ["en", "cs"])
    def test_the_head_fields_land_in_the_head(self, language: EmailLanguage):
        """
        GIVEN a rendered email
        WHEN its html is read
        THEN the language, the subject and the preheader each appear where the layout puts them
        """
        # GIVEN
        copy = VERIFICATION_COPIES[language]

        # WHEN
        html = _render(language=language).html

        # THEN
        assert f'<html lang="{copy.lang}"' in html
        assert f"<title>{html_lib.escape(copy.subject, quote=True)}</title>" in html
        assert f">{html_lib.escape(copy.preheader, quote=True)}</div>" in html

    @pytest.mark.parametrize("language", ["en", "cs"])
    def test_the_text_part_carries_every_copy_field(self, language: EmailLanguage):
        """
        GIVEN a rendered email
        WHEN its text part is read
        THEN the wordmark, heading, body, button label, not-you and footer are in it
        """
        # GIVEN
        copy = VERIFICATION_COPIES[language]

        # WHEN
        text = _render(language=language).text

        # THEN
        for value in (
            copy.wordmark,
            copy.heading,
            copy.body,
            f"{copy.button_label}:",
            copy.not_you,
            copy.footer,
        ):
            assert value in text


class TestRenderedText:
    """The plain-text alternative carries the same message without markup."""

    def test_paragraphs_are_the_copy_in_order(self):
        """
        GIVEN a verification link and a lifetime of a day
        WHEN the email is rendered
        THEN the text is the wordmark, heading, body, link, expiry with not-you, footer
        """
        # WHEN
        text = _render().text

        # THEN
        assert text.split("\n\n") == [
            "BeCoMe",
            _HEADING,
            _BODY,
            f"{_BUTTON}:\n{_URL}",
            f"The link expires in 24 hours. {_NOT_YOU}",
            _FOOTER,
        ]

    def test_url_stands_alone_on_a_line(self):
        """
        GIVEN a rendered email
        WHEN its text is split into lines
        THEN one line is exactly the URL
        """
        # WHEN
        lines = _render().text.splitlines()

        # THEN
        assert _URL in lines

    def test_holds_no_html_tags(self):
        """
        GIVEN a rendered email
        WHEN its text is read
        THEN no tag is in it
        """
        # WHEN
        text = _render().text

        # THEN
        assert not re.search(r"</?[A-Za-z]", text)

    def test_url_appears_raw(self):
        """
        GIVEN a URL holding an ampersand, a double quote and an angle bracket
        WHEN the email is rendered
        THEN the text part holds it as given, since plain text is not markup
        """
        # WHEN
        text = _render(url=_HOSTILE_URL).text

        # THEN
        assert _HOSTILE_URL in text.splitlines()
        assert "&amp;" not in text


class TestCzechRendering:
    """The same message in Czech, with no English left in it."""

    def test_the_document_declares_czech(self):
        """
        GIVEN a verification link
        WHEN the email is rendered in Czech
        THEN the html declares Czech
        """
        # WHEN
        html = _render(language="cs").html

        # THEN
        assert '<html lang="cs"' in html

    def test_heading_sits_inside_an_h1(self):
        """
        GIVEN a Czech email
        WHEN its html is read
        THEN the Czech heading is the content of an h1 element
        """
        # WHEN
        html = _render(language="cs").html

        # THEN
        assert re.search(rf"<h1[^>]*>\s*{_CS_HEADING}\s*</h1>", html)

    def test_button_label_sits_inside_the_link_to_the_url(self):
        """
        GIVEN a Czech email
        WHEN its html is read
        THEN the Czech button label is the text of the anchor whose href is the URL
        """
        # GIVEN
        pattern = rf'<a href="{re.escape(_URL)}"[^>]*>\s*{_CS_BUTTON}\s*</a>'

        # WHEN
        html = _render(language="cs").html

        # THEN
        assert re.search(pattern, html)

    def test_text_part_is_the_czech_copy_in_order(self):
        """
        GIVEN a verification link and a lifetime of a day
        WHEN the email is rendered in Czech
        THEN the text part is the Czech copy, with the link alone under the button label
        """
        # WHEN
        text = _render(language="cs").text

        # THEN
        assert text.split("\n\n") == [
            "BeCoMe",
            _CS_HEADING,
            _CS_BODY,
            f"{_CS_BUTTON}:\n{_URL}",
            f"Odkaz platí 24 hodin. {_CS_NOT_YOU}",
            _CS_FOOTER,
        ]

    def test_carries_the_preheader_and_footer(self):
        """
        GIVEN a Czech email
        WHEN its html is read
        THEN the Czech preheader, fallback, body, not-you and footer are present
        """
        # WHEN
        html = _render(language="cs").html

        # THEN
        for value in (_CS_PREHEADER, _CS_FALLBACK, _CS_FOOTER, _CS_NOT_YOU, _CS_BODY):
            assert html_lib.escape(value, quote=True) in html

    @pytest.mark.parametrize(
        "sentence",
        [_SUBJECT, _PREHEADER, _HEADING, _BODY, _BUTTON, _FALLBACK, _NOT_YOU, _FOOTER],
    )
    def test_no_english_sentence_survives(self, sentence: str):
        """
        GIVEN a Czech email
        WHEN its html and text are searched for each English sentence
        THEN none is found
        """
        # WHEN
        rendered = _render(language="cs")

        # THEN
        assert html_lib.escape(sentence, quote=True) not in rendered.html
        assert sentence not in rendered.text

    @pytest.mark.parametrize("minutes", [1, 2, 5, 60, 120, 1440, 90])
    def test_the_lifetime_sentence_has_no_english_word(self, minutes: int):
        """
        GIVEN any lifetime
        WHEN the email is rendered in Czech
        THEN the sentence about it is Czech throughout
        """
        # WHEN
        rendered = _render(minutes=minutes, language="cs")

        # THEN
        body = rendered.html.split("<body")[1].lower()
        for word in ("hour", "minute", "expire"):
            assert word not in body
            assert word not in rendered.text.lower()

    @pytest.mark.parametrize(
        ("minutes", "phrase"),
        [
            (60, "1 hodinu"),
            (120, "2 hodiny"),
            (180, "3 hodiny"),
            (240, "4 hodiny"),
            (300, "5 hodin"),
            (1440, "24 hodin"),
            (1, "1 minutu"),
            (2, "2 minuty"),
            (4, "4 minuty"),
            (5, "5 minut"),
            (45, "45 minut"),
            (90, "90 minut"),
        ],
    )
    def test_lifetime_takes_the_czech_form_for_its_number(self, minutes: int, phrase: str):
        """
        GIVEN a lifetime
        WHEN the email is rendered in Czech
        THEN the unit is declined for the number, in the html and in the text
        """
        # WHEN
        rendered = _render(minutes=minutes, language="cs")

        # THEN
        assert f"Odkaz platí {phrase}." in rendered.html
        assert f"Odkaz platí {phrase}." in rendered.text


def _render_reset(
    url: str = _RESET_URL, minutes: int = 60, language: EmailLanguage = "en"
) -> RenderedEmail:
    """Render the password-reset email for a link, a lifetime in minutes and a language."""
    return render_password_reset_email(url, minutes, language)


@pytest.mark.parametrize("language", ["en", "cs"])
class TestPasswordResetEmail:
    """The reset email is the same layout with its own copy, in either language."""

    def test_the_copy_is_the_agreed_wording(self, language: EmailLanguage):
        """
        GIVEN the reset copy of a language
        WHEN its text fields are compared with the agreed wording
        THEN every one matches
        """
        # GIVEN
        copy = asdict(PASSWORD_RESET_COPIES[language])

        # THEN
        assert {name: copy[name] for name in _RESET[language]} == _RESET[language]
        assert copy["expiry"] == _RESET_EXPIRY[language]
        assert copy["lang"] == language

    def test_the_subject_is_the_title(self, language: EmailLanguage):
        """
        GIVEN a reset link
        WHEN the email is rendered
        THEN the subject is the reset subject and the document title carries it
        """
        # WHEN
        rendered = _render_reset(language=language)

        # THEN
        assert rendered.subject == _RESET[language]["subject"]
        assert f"<title>{html_lib.escape(rendered.subject, quote=True)}</title>" in rendered.html

    def test_html_is_one_complete_document_in_the_language(self, language: EmailLanguage):
        """
        GIVEN a reset link
        WHEN the email is rendered
        THEN the html is a full document declaring the language
        """
        # WHEN
        html = _render_reset(language=language).html

        # THEN
        assert html.lstrip().startswith("<!DOCTYPE html>")
        assert f'<html lang="{language}"' in html
        assert html.rstrip().endswith("</html>")

    def test_heading_button_and_links_carry_the_copy_and_the_url(self, language: EmailLanguage):
        """
        GIVEN a reset link
        WHEN the email is rendered
        THEN the heading is the content of the h1, and the button and the fallback both link
            to the URL
        """
        # GIVEN
        copy = _RESET[language]
        button = rf'<a href="{re.escape(_RESET_URL)}"[^>]*>\s*{copy["button_label"]}\s*</a>'

        # WHEN
        html = _render_reset(language=language).html

        # THEN
        assert re.search(rf"<h1[^>]*>\s*{copy['heading']}\s*</h1>", html)
        assert re.search(button, html)
        assert f'<a href="{_RESET_URL}" class="fallback-link"' in html
        assert f">{_RESET_URL}</a>" in html

    def test_every_sentence_of_the_copy_is_in_the_html(self, language: EmailLanguage):
        """
        GIVEN a reset link
        WHEN the email is rendered
        THEN the text nodes of the html hold every visible field of the copy, and the
            preheader sits in its hidden line
        """
        # GIVEN
        copy = _RESET[language]
        rendered = _render_reset(language=language)
        parser = _TextNodes()
        parser.feed(rendered.html)
        nodes = [html_lib.unescape(node) for node in parser.nodes]

        # THEN
        for name in ("heading", "body", "button_label", "fallback", "not_you", "footer"):
            assert any(copy[name] in node for node in nodes), name
        assert f">{html_lib.escape(copy['preheader'], quote=True)}</div>" in rendered.html

    def test_url_is_escaped_in_the_html_and_raw_in_the_text(self, language: EmailLanguage):
        """
        GIVEN a URL holding an ampersand, a double quote and an angle bracket
        WHEN the email is rendered
        THEN the html carries the escaped form in both hrefs and the visible text and never
            the raw one, while the text part holds it as given
        """
        # WHEN
        rendered = _render_reset(url=_HOSTILE_URL, language=language)

        # THEN
        assert _HOSTILE_URL not in rendered.html
        assert rendered.html.count(_HOSTILE_URL_ESCAPED) == 3
        assert rendered.html.count(f'href="{_HOSTILE_URL_ESCAPED}"') == 2
        assert _HOSTILE_URL in rendered.text.splitlines()

    def test_text_part_is_the_copy_in_order(self, language: EmailLanguage):
        """
        GIVEN a reset link and a lifetime of an hour
        WHEN the email is rendered
        THEN the text part is the copy in order, with the link alone under the button label
            and no markup
        """
        # GIVEN
        copy = _RESET[language]
        window = {"en": "1 hour", "cs": "1 hodinu"}[language]
        expiry = _RESET_EXPIRY[language].format(window=window)

        # WHEN
        text = _render_reset(language=language).text

        # THEN
        assert text.split("\n\n") == [
            "BeCoMe",
            copy["heading"],
            copy["body"],
            f"{copy['button_label']}:\n{_RESET_URL}",
            f"{expiry} {copy['not_you']}",
            copy["footer"],
        ]
        assert not re.search(r"</?[A-Za-z]", text)
        assert "$" not in text

    @pytest.mark.parametrize("minutes", [1, 30, 60, 90, 120, 1440])
    def test_the_lifetime_is_stated_in_the_html_and_the_text(
        self, language: EmailLanguage, minutes: int
    ):
        """
        GIVEN a lifetime
        WHEN the reset email is rendered
        THEN the expiry sentence states it in that language, in both parts
        """
        # GIVEN
        sentence = _RESET_EXPIRY[language].format(window=format_lifetime(minutes, language))

        # WHEN
        rendered = _render_reset(minutes=minutes, language=language)

        # THEN
        assert sentence in rendered.html
        assert sentence in rendered.text


class TestPasswordResetEmailInCzech:
    """No English survives in the Czech reset email."""

    @pytest.mark.parametrize("field", list(_RESET["en"]))
    def test_no_english_sentence_survives(self, field: str):
        """
        GIVEN a Czech reset email
        WHEN its html and text are searched for each English sentence of the reset copy
        THEN none is found
        """
        # GIVEN
        sentence = _RESET["en"][field]

        # WHEN
        rendered = _render_reset(language="cs")

        # THEN
        assert html_lib.escape(sentence, quote=True) not in rendered.html
        assert sentence not in rendered.text

    @pytest.mark.parametrize("minutes", [1, 2, 5, 30, 60, 120])
    def test_the_lifetime_sentence_has_no_english_word(self, minutes: int):
        """
        GIVEN any lifetime
        WHEN the reset email is rendered in Czech
        THEN the sentence about it is Czech throughout
        """
        # WHEN
        rendered = _render_reset(minutes=minutes, language="cs")

        # THEN
        body = rendered.html.split("<body")[1].lower()
        for word in ("hour", "minute", "expire"):
            assert word not in body
            assert word not in rendered.text.lower()


_LOGIN_URL = "https://app.example/login"
_NOTICE_RESET_URL = "https://app.example/forgot-password"
_HOSTILE_RESET_URL = 'https://app.example/reset?a=1&b="x"<z'
_HOSTILE_RESET_URL_ESCAPED = "https://app.example/reset?a=1&amp;b=&quot;x&quot;&lt;z"

# The notice copy as it must read, per language. It has no expiry sentence.
_NOTICE = {
    "en": {
        "subject": "You already have a BeCoMe account",
        "preheader": "Someone tried to sign up with this address. Your account has not changed.",
        "heading": "You already have an account",
        "body": (
            "Someone tried to sign up for BeCoMe with this email address, which already has "
            "an account. If it was you, sign in instead."
        ),
        "button_label": "Sign in",
        "fallback": "If the button doesn't work, copy and paste this link into your browser:",
        "secondary_lead": "Forgot your password?",
        "secondary_link": "Reset it.",
        "not_you": (
            "If it wasn't you, you don't have to do anything. Your account has not changed."
        ),
        "footer": (
            "You're receiving this email from BeCoMe at becomify.app because someone entered "
            "this address in the sign-up form. It's an automatic message, so please don't reply."
        ),
    },
    "cs": {
        "subject": "BeCoMe: účet s touto adresou už existuje",
        "preheader": "Někdo se pokusil zaregistrovat pod touto adresou. Váš účet zůstává beze změny.",
        "heading": "Účet už máte",
        "body": (
            "Někdo se pokusil zaregistrovat do aplikace BeCoMe pod touto e-mailovou adresou, "
            "ke které už účet existuje. Pokud jste to byli vy, stačí se přihlásit."
        ),
        "button_label": "Přihlásit se",
        "fallback": "Pokud tlačítko nefunguje, zkopírujte tento odkaz do prohlížeče:",
        "secondary_lead": "Zapomněli jste heslo?",
        "secondary_link": "Obnovte si ho.",
        "not_you": "Pokud jste to nebyli vy, nemusíte dělat nic. Váš účet zůstává beze změny.",
        "footer": (
            "Tento e-mail vám posílá aplikace BeCoMe (becomify.app), protože někdo zadal tuto "
            "adresu do registračního formuláře. Jde o automatickou zprávu, na kterou prosím "
            "neodpovídejte."
        ),
    },
}

# How the secondary link reads in the text part, where the link text loses its full stop.
_NOTICE_TEXT_LINK = {
    "en": "Forgot your password? Reset it:",
    "cs": "Zapomněli jste heslo? Obnovte si ho:",
}


def _render_notice(
    login_url: str = _LOGIN_URL,
    reset_url: str = _NOTICE_RESET_URL,
    language: EmailLanguage = "en",
) -> RenderedEmail:
    """Render the registration notice for a sign-in link, a reset link and a language."""
    return render_registration_notice_email(login_url, reset_url, language)


@pytest.mark.parametrize("language", ["en", "cs"])
class TestRegistrationNoticeEmail:
    """The notice is the same layout with two links, no expiry and a closing sentence."""

    def test_the_copy_is_the_agreed_wording(self, language: EmailLanguage):
        """
        GIVEN the notice copy of a language
        WHEN its text fields are compared with the agreed wording
        THEN every one matches, and the copy carries no expiry sentence
        """
        # GIVEN
        copy = asdict(REGISTRATION_NOTICE_COPIES[language])

        # THEN
        assert {name: copy[name] for name in _NOTICE[language]} == _NOTICE[language]
        assert copy["expiry"] == ""
        assert copy["lang"] == language

    def test_the_subject_is_the_title(self, language: EmailLanguage):
        """
        GIVEN a notice
        WHEN it is rendered
        THEN the subject is the notice subject and the document title carries it
        """
        # WHEN
        rendered = _render_notice(language=language)

        # THEN
        assert rendered.subject == _NOTICE[language]["subject"]
        assert f"<title>{html_lib.escape(rendered.subject, quote=True)}</title>" in rendered.html

    def test_html_is_one_complete_document_in_the_language(self, language: EmailLanguage):
        """
        GIVEN a notice
        WHEN it is rendered
        THEN the html is a full document declaring the language, with no placeholder left
        """
        # WHEN
        html = _render_notice(language=language).html

        # THEN
        assert html.lstrip().startswith("<!DOCTYPE html>")
        assert f'<html lang="{language}"' in html
        assert html.rstrip().endswith("</html>")
        assert "$" not in html

    def test_heading_button_and_links_carry_the_copy_and_the_urls(self, language: EmailLanguage):
        """
        GIVEN a notice
        WHEN it is rendered
        THEN the heading is the content of the h1, the button and the fallback link to the
            sign-in URL, and the secondary link points at the reset URL
        """
        # GIVEN
        copy = _NOTICE[language]
        button = rf'<a href="{re.escape(_LOGIN_URL)}"[^>]*>\s*{copy["button_label"]}\s*</a>'
        secondary = (
            rf'<a href="{re.escape(_NOTICE_RESET_URL)}"[^>]*>\s*{copy["secondary_link"]}\s*</a>'
        )

        # WHEN
        html = _render_notice(language=language).html

        # THEN
        assert re.search(rf"<h1[^>]*>\s*{copy['heading']}\s*</h1>", html)
        assert re.search(button, html)
        assert f'<a href="{_LOGIN_URL}" class="fallback-link"' in html
        assert f">{_LOGIN_URL}</a>" in html
        assert re.search(secondary, html)
        assert html.count(_NOTICE_RESET_URL) == 1

    def test_the_secondary_link_sits_between_the_fallback_and_the_closing_line(
        self, language: EmailLanguage
    ):
        """
        GIVEN a notice
        WHEN its html is read in order
        THEN the button comes first, then the fallback link, then the reset question with its
            link, then the closing sentence, then the footer
        """
        # GIVEN
        copy = _NOTICE[language]
        html = _render_notice(language=language).html
        markers = [
            html.index(f">{copy['button_label']}</a>"),
            html.index(f">{_LOGIN_URL}</a>"),
            html.index(copy["secondary_lead"]),
            html.index(f'href="{_NOTICE_RESET_URL}"'),
            html.index(html_lib.escape(copy["not_you"], quote=True)),
            html.index(html_lib.escape(copy["footer"], quote=True)),
        ]

        # THEN
        assert markers == sorted(markers)

    def test_every_sentence_of_the_copy_is_in_the_html(self, language: EmailLanguage):
        """
        GIVEN a notice
        WHEN it is rendered
        THEN the text nodes of the html hold every visible field of the copy, and the
            preheader sits in its hidden line
        """
        # GIVEN
        copy = _NOTICE[language]
        rendered = _render_notice(language=language)
        parser = _TextNodes()
        parser.feed(rendered.html)
        nodes = [html_lib.unescape(node) for node in parser.nodes]

        # THEN
        visible = ("heading", "body", "button_label", "fallback", "secondary_lead")
        for name in (*visible, "secondary_link", "not_you", "footer"):
            assert any(copy[name] in node for node in nodes), name
        assert f">{html_lib.escape(copy['preheader'], quote=True)}</div>" in rendered.html

    def test_both_urls_are_escaped_in_the_html_and_raw_in_the_text(self, language: EmailLanguage):
        """
        GIVEN two URLs each holding an ampersand, a double quote and an angle bracket
        WHEN the notice is rendered
        THEN the html carries the escaped forms and never the raw ones, while the text part
            holds each as given on a line of its own
        """
        # WHEN
        rendered = _render_notice(
            login_url=_HOSTILE_URL, reset_url=_HOSTILE_RESET_URL, language=language
        )

        # THEN
        assert _HOSTILE_URL not in rendered.html
        assert _HOSTILE_RESET_URL not in rendered.html
        assert rendered.html.count(_HOSTILE_URL_ESCAPED) == 3
        assert rendered.html.count(f'href="{_HOSTILE_URL_ESCAPED}"') == 2
        assert rendered.html.count(f'href="{_HOSTILE_RESET_URL_ESCAPED}"') == 1
        assert {_HOSTILE_URL, _HOSTILE_RESET_URL} <= set(rendered.text.splitlines())

    def test_text_part_is_the_copy_in_order(self, language: EmailLanguage):
        """
        GIVEN a notice
        WHEN it is rendered
        THEN the text part is the copy in order, each link alone under its label, no markup
        """
        # GIVEN
        copy = _NOTICE[language]

        # WHEN
        text = _render_notice(language=language).text

        # THEN
        assert text.split("\n\n") == [
            "BeCoMe",
            copy["heading"],
            copy["body"],
            f"{copy['button_label']}:\n{_LOGIN_URL}",
            f"{_NOTICE_TEXT_LINK[language]}\n{_NOTICE_RESET_URL}",
            copy["not_you"],
            copy["footer"],
        ]
        assert not re.search(r"</?[A-Za-z]", text)

    def test_there_is_no_expiry_line_and_no_empty_paragraph(self, language: EmailLanguage):
        """
        GIVEN a notice, which carries no lifetime
        WHEN its html and text are read
        THEN no expiry sentence is in either, no paragraph is empty, and the single rule
            above the closing sentence is the only border the card body draws
        """
        # GIVEN
        closing = html_lib.escape(_NOTICE[language]["not_you"], quote=True)

        # WHEN
        rendered = _render_notice(language=language)

        # THEN
        assert not re.search(r"(expires|platí)", rendered.html + rendered.text)
        assert not re.search(r"<p[^>]*>\s*</p>", rendered.html)
        assert rendered.html.count("border-top:") == 1
        assert re.search(
            rf'<p class="muted rule" style="margin:0;[^"]*">{closing}</p>', rendered.html
        )


class TestRegistrationNoticeInCzech:
    """No English survives in the Czech notice."""

    @pytest.mark.parametrize("field", list(_NOTICE["en"]))
    def test_no_english_sentence_survives(self, field: str):
        """
        GIVEN a Czech notice
        WHEN its html and text are searched for each English sentence of the notice copy
        THEN none is found
        """
        # GIVEN
        sentence = _NOTICE["en"][field]

        # WHEN
        rendered = _render_notice(language="cs")

        # THEN
        assert html_lib.escape(sentence, quote=True) not in rendered.html
        assert sentence not in rendered.text


class TestSecondaryLinkRow:
    """A copy with a second link gets one more row, between the fallback and the closing line."""

    def test_the_row_carries_the_escaped_link_and_sits_before_the_expiry(self):
        """
        GIVEN a copy with a question and a second link, and a URL that needs escaping
        WHEN it is rendered with a lifetime
        THEN the html holds the row with the escaped link between the fallback link and the
            expiry sentence, and the text part holds the link alone under the question
        """
        # GIVEN
        copy = replace(
            VERIFICATION_COPIES["en"], secondary_lead="Lost it?", secondary_link="Try again."
        )

        # WHEN
        rendered = messages._render(copy, _URL, "en", expiry_minutes=60, secondary_url=_HOSTILE_URL)

        # THEN
        row = f'Lost it? <a href="{_HOSTILE_URL_ESCAPED}" class="fallback-link"'
        assert _HOSTILE_URL not in rendered.html
        assert rendered.html.index(f">{_URL}</a>") < rendered.html.index(row)
        assert rendered.html.index(row) < rendered.html.index("The link expires in 1 hour.")
        assert "Try again.</a></p>" in rendered.html
        assert "Lost it? Try again:" in rendered.text
        assert _HOSTILE_URL in rendered.text.splitlines()


class TestACopyWithNoClosingLines:
    """A message with neither an expiry nor a closing sentence leaves no gap behind."""

    def test_neither_part_holds_an_empty_paragraph(self):
        """
        GIVEN a copy with an empty closing sentence, rendered with no lifetime
        WHEN both parts are read
        THEN the text part has no run of blank lines and the html has no empty paragraph
            and no rule
        """
        # GIVEN
        copy = replace(VERIFICATION_COPIES["en"], not_you="")

        # WHEN
        rendered = messages._render(copy, _URL, "en")

        # THEN
        assert "\n\n\n" not in rendered.text
        assert "" not in rendered.text.split("\n\n")
        assert rendered.text.split("\n\n")[-1] == copy.footer
        assert not re.search(r"<p[^>]*>\s*</p>", rendered.html)
        assert "border-top:" not in rendered.html


@pytest.mark.parametrize("language", ["en", "cs"])
@pytest.mark.parametrize(
    ("copies", "render"),
    [
        (VERIFICATION_COPIES, render_verification_email),
        (PASSWORD_RESET_COPIES, render_password_reset_email),
    ],
    ids=["verification", "password_reset"],
)
class TestTwoClosingRows:
    """The expiry sentence and the "not you" line close the card as two rows."""

    def test_the_rule_spacing_and_order_of_the_two_closing_rows(
        self, copies: dict[str, EmailCopy], render, language: EmailLanguage
    ):
        """
        GIVEN a verification or password-reset email, which carries an expiry sentence and a
            "not you" line
        WHEN its html is read
        THEN the fallback line, the expiry sentence, the "not you" line and the footer come in
            that order, the one rule sits on the expiry row, and only the expiry row keeps a
            bottom margin while the last row has none
        """
        # GIVEN
        copy = copies[language]
        expiry = html_lib.escape(
            copy.expiry.format(window=format_lifetime(60, language)), quote=True
        )
        not_you = html_lib.escape(copy.not_you, quote=True)

        # WHEN
        html = render(_URL, 60, language).html

        # THEN
        fallback_at = html.index(html_lib.escape(copy.fallback, quote=True))
        expiry_at = html.index(expiry)
        not_you_at = html.index(not_you)
        footer_at = html.index(html_lib.escape(copy.footer, quote=True))
        assert fallback_at < expiry_at < not_you_at < footer_at
        assert html.count("border-top:") == 1
        assert html.index("border-top:") < expiry_at
        first = re.search(rf'<p class="muted rule" style="([^"]*)">{re.escape(expiry)}</p>', html)
        last = re.search(rf'<p class="muted" style="([^"]*)">{re.escape(not_you)}</p>', html)
        assert first is not None
        assert last is not None
        assert first.group(1).startswith("margin:0 0 8px 0;")
        assert "border-top:" in first.group(1)
        assert last.group(1).startswith("margin:0;")
        assert "border-top:" not in last.group(1)


class TestFormatLifetime:
    """The lifetime wording that every email shares."""

    @pytest.mark.parametrize(
        ("minutes", "expected"),
        [
            (60, "1 hour"),
            (120, "2 hours"),
            (1440, "24 hours"),
            (1, "1 minute"),
            (2, "2 minutes"),
            (30, "30 minutes"),
            (45, "45 minutes"),
            (90, "90 minutes"),
        ],
    )
    def test_english_wording(self, minutes: int, expected: str):
        """
        GIVEN a lifetime in minutes
        WHEN it is written in English
        THEN whole hours read as hours and the rest as minutes
        """
        # WHEN
        window = format_lifetime(minutes, "en")

        # THEN
        assert window == expected

    @pytest.mark.parametrize("language", get_args(EmailLanguage))
    def test_every_supported_language_has_unit_words(self, language: EmailLanguage):
        """
        GIVEN a language the email type supports
        WHEN a lifetime is written in it and the three emails are rendered in it
        THEN all succeed and yield text, so a language missing from a table fails here
        """
        # WHEN
        window = format_lifetime(60, language)
        rendered = [
            render_verification_email("https://example.test/verify?token=abc", 60, language),
            render_password_reset_email("https://example.test/reset?token=abc", 60, language),
            render_registration_notice_email(
                "https://example.test/login", "https://example.test/forgot-password", language
            ),
        ]

        # THEN
        assert window
        for message in rendered:
            assert message.subject
            assert message.html
            assert message.text


class TestLayoutFile:
    """The layout is a language-free data file."""

    @pytest.fixture
    def layout(self) -> str:
        """Read the layout file as shipped."""
        return _layout()

    def test_holds_no_images(self, layout: str):
        """
        GIVEN the layout file
        WHEN it is searched for image elements
        THEN there are none
        """
        # THEN
        assert "<img" not in layout.lower()

    def test_holds_no_url_of_its_own(self, layout: str):
        """
        GIVEN the layout file
        WHEN it is searched for links
        THEN none is baked in, since the only link comes from the caller
        """
        # THEN
        assert "http" not in layout.lower()

    def test_holds_no_words_of_its_own(self, layout: str):
        """
        GIVEN the layout file
        WHEN its visible text is collected
        THEN every piece is a placeholder, so a language is a matter of swapping strings
        """
        # WHEN
        parser = _TextNodes()
        parser.feed(layout)

        # THEN
        assert parser.nodes
        assert all(re.fullmatch(r"\$[a-z_]+", node) for node in parser.nodes), parser.nodes

    def test_every_table_is_presentational(self, layout: str):
        """
        GIVEN the layout file, including its conditional comments
        WHEN each table opening is inspected
        THEN it carries role="presentation"
        """
        # WHEN
        tables = re.findall(r"<table\b[^>]*>", layout, flags=re.IGNORECASE)

        # THEN
        assert len(tables) >= 3
        assert all('role="presentation"' in table for table in tables), tables

    def test_declares_the_head_metadata(self, layout: str):
        """
        GIVEN the layout file
        WHEN its head is read
        THEN charset, viewport and both colour-scheme hints are declared
        """
        # THEN
        assert '<meta charset="utf-8"' in layout.lower()
        assert 'name="viewport"' in layout
        assert 'name="color-scheme" content="light dark"' in layout
        assert 'name="supported-color-schemes" content="light dark"' in layout
        assert "prefers-color-scheme: dark" in layout
