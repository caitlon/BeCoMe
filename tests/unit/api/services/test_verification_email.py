"""Tests for the rendered account-verification email and its layout file.

The layout is a data file with placeholders and no words of its own, so a later
language can be added by swapping the strings alone. The renderer is a pure
function, so every test here calls it directly with no settings and no network.
"""

import html as html_lib
import re
from html.parser import HTMLParser
from importlib.resources import files

import pytest

from api.services.email.verification_email import RenderedEmail, render_verification_email

_URL = "https://app.example/verify-email?token=abc"
_HOSTILE_URL = 'https://app.example/verify?a=1&b="x"<y'
_HOSTILE_URL_ESCAPED = "https://app.example/verify?a=1&amp;b=&quot;x&quot;&lt;y"
_WINDOW = "24 hours"

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


def _render(url: str = _URL, window: str = _WINDOW) -> RenderedEmail:
    """Render the verification email for a link and an expiry window."""
    return render_verification_email(url, window)


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
        WHEN the email is rendered
        THEN the subject is the fixed English subject line
        """
        # WHEN
        rendered = _render()

        # THEN
        assert rendered.subject == _SUBJECT

    def test_title_element_carries_the_subject(self):
        """
        GIVEN a rendered email
        WHEN its html is read
        THEN the document title equals the subject
        """
        # GIVEN
        rendered = _render()

        # WHEN
        title = f"<title>{rendered.subject}</title>"

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
        GIVEN a lifetime text of one hour
        WHEN the email is rendered
        THEN the html says so and never mentions another window
        """
        # WHEN
        rendered = _render(window="1 hour")

        # THEN
        assert "The link expires in 1 hour." in rendered.html
        assert "24 hours" not in rendered.html

    @pytest.mark.parametrize(
        ("field", "raw", "escaped", "occurrences"),
        [
            ("url", _HOSTILE_URL, _HOSTILE_URL_ESCAPED, 3),
            ("window", "<b>1 hour</b>", "&lt;b&gt;1 hour&lt;/b&gt;", 1),
        ],
    )
    def test_caller_values_are_escaped_everywhere_they_appear(
        self, field: str, raw: str, escaped: str, occurrences: int
    ):
        """
        GIVEN a link or a lifetime text holding markup characters
        WHEN the email is rendered
        THEN the html carries the escaped form wherever the value appears, and the raw one
            nowhere
        """
        # GIVEN
        arguments = {field: raw}

        # WHEN
        rendered = _render(**arguments)

        # THEN
        assert raw not in rendered.html
        assert rendered.html.count(escaped) == occurrences

    def test_url_sits_in_both_hrefs_and_as_visible_text(self):
        """
        GIVEN a URL holding an ampersand, a double quote and an angle bracket
        WHEN the email is rendered
        THEN the button and the fallback link both point at it, and it is shown as text
        """
        # WHEN
        rendered = _render(url=_HOSTILE_URL)

        # THEN
        assert rendered.html.count(f'href="{_HOSTILE_URL_ESCAPED}"') == 2
        assert f">{_HOSTILE_URL_ESCAPED}</a>" in rendered.html

    def test_no_placeholder_survives(self):
        """
        GIVEN a rendered email
        WHEN its html and text are read
        THEN neither holds a dollar sign left over from the layout
        """
        # WHEN
        rendered = _render()

        # THEN
        assert "$" not in rendered.html
        assert "$" not in rendered.text


class TestRenderedText:
    """The plain-text alternative carries the same message without markup."""

    def test_paragraphs_are_the_copy_in_order(self):
        """
        GIVEN a verification link and a lifetime text
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
            f"The link expires in {_WINDOW}. {_NOT_YOU}",
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


class TestLayoutFile:
    """The layout is a language-free data file."""

    @pytest.fixture
    def layout(self) -> str:
        """Read the layout file as shipped."""
        return files("api.services.email").joinpath("layout.html").read_text(encoding="utf-8")

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
