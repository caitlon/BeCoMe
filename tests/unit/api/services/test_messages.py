"""Tests for the rendered transactional emails and their shared layout file.

The layout is a data file with placeholders and no words of its own, so a language is
added by swapping the strings alone. The renderers are pure functions, so every test
here calls them directly with no settings and no network.
"""

import hashlib
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
    VERIFICATION_COPIES,
    EmailCopy,
    RenderedEmail,
    format_lifetime,
    render_password_reset_email,
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


# SHA-256 over subject, html and text of the verification and password-reset emails as first
# shipped in the shared layout. Whatever builds the rows under the link must not move a byte
# of them. A deliberate change to either email means new digests here.
_GOLDEN = [
    (
        "verification",
        "en",
        1440,
        "0477df76cfab3c0dafabbd46ff8faafb2f2847cc8f5f3dfeca52db690b865414",  # pragma: allowlist secret
    ),
    (
        "verification",
        "cs",
        60,
        "2dd61b9f96df7967b325d2cfbc9e753dc36a15283ce75108bc3f501afcca1206",  # pragma: allowlist secret
    ),
    (
        "password_reset",
        "en",
        60,
        "6281ad20697ac7c4c25a32f5a1a6c45e8efd87932232f897ed1abbafc917de56",  # pragma: allowlist secret
    ),
    (
        "password_reset",
        "cs",
        30,
        "9af44ef4c079eab8d147e8b0763539bc0a25412e4edf5cfc19440ad2ead4972b",  # pragma: allowlist secret
    ),
]


@pytest.mark.parametrize(("kind", "language", "minutes", "digest"), _GOLDEN)
def test_verification_and_reset_emails_keep_their_bytes(
    kind: str, language: EmailLanguage, minutes: int, digest: str
):
    """
    GIVEN the verification and the password-reset email, each in a language and a lifetime
    WHEN they are rendered
    THEN the digest of subject, html and text is the one recorded when the two shared the
        layout, so the way rows are built cannot move a byte of either
    """
    # GIVEN
    render = {
        "verification": render_verification_email,
        "password_reset": render_password_reset_email,
    }[kind]

    # WHEN
    rendered = render(_URL, minutes, language)

    # THEN
    parts = "\0".join((rendered.subject, rendered.html, rendered.text))
    assert hashlib.sha256(parts.encode()).hexdigest() == digest


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
        WHEN a lifetime is written in it and the two emails are rendered in it
        THEN all succeed and yield text, so a language missing from a table fails here
        """
        # WHEN
        window = format_lifetime(60, language)
        rendered = [
            render_verification_email("https://example.test/verify?token=abc", 60, language),
            render_password_reset_email("https://example.test/reset?token=abc", 60, language),
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
