"""Regression tests for the SPA's Content-Security-Policy.

frontend/nginx.conf serves the React SPA and carries its CSP. The API is a
separate origin on every deploy (https://api.<domain>), so any directive that
has to reach the API names the placeholder __API_ORIGIN__, which
frontend/Dockerfile substitutes with the real origin at image build time.

Two directives need it, for different reasons: connect-src covers fetch/XHR,
and img-src covers profile photos, which the API serves as image bytes
(GET /users/{id}/photo) rendered in <img> tags. Missing img-src is a silent
failure: the browser drops the request before it leaves the tab, so nothing
appears in the API logs and the avatar simply never renders. That shipped to
production once; these tests exist so it cannot ship again.

Cloudflare's Turnstile host is named for the same kind of reason and fails the
same silent way: script-src has to allow the widget's script and frame-src the
iframe it draws itself in. A policy missing either one leaves every auth form
on a deploy that has a sitekey permanently unsubmittable.

The page's one inline script (the pre-paint theme and language script in index.html) is
allowed by its sha256 hash, never by 'unsafe-inline'. Changing one byte of it changes the
hash, so a test recomputes it and fails until nginx.conf carries the new value.

The config is plain text with no runtime the test suite can exercise, so this
module parses it, the same way test_frontend_case_studies.py parses
caseStudies.ts.
"""

import base64
import hashlib
import re
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_NGINX_CONF = _PROJECT_ROOT / "frontend" / "nginx.conf"
_DOCKERFILE = _PROJECT_ROOT / "frontend" / "Dockerfile"
_INDEX_HTML = _PROJECT_ROOT / "frontend" / "index.html"

_CSP_HEADER = re.compile(r'add_header\s+Content-Security-Policy\s+"([^"]*)"')

# Directives that must reach the API origin. nginx repeats the whole header in
# every location block that sets one of its own, so each copy is checked.
_API_ORIGIN_DIRECTIVES = ("connect-src", "img-src")

# The bot check's widget (frontend/src/lib/turnstile.ts) loads its script from this
# host and renders its challenge in an iframe served by it, so both directives below
# have to name it, in every copy, for the same inheritance reason.
_TURNSTILE_HOST = "https://challenges.cloudflare.com"
_TURNSTILE_DIRECTIVES = ("script-src", "frame-src")

# Headers every add_header block must repeat, for the same inheritance reason.
_REQUIRED_HEADERS = (
    "X-Frame-Options",
    "X-Content-Type-Options",
    "Referrer-Policy",
    "Content-Security-Policy",
    "Strict-Transport-Security",
)


def _csp_headers() -> list[str]:
    """Return every Content-Security-Policy value declared in nginx.conf."""
    return _CSP_HEADER.findall(_NGINX_CONF.read_text(encoding="utf-8"))


def _header_counts() -> dict[str, int]:
    """Count how many times each header is actually declared in nginx.conf.

    Comment lines are dropped first: the config explains the inheritance trap in prose
    that mentions ``add_header``, and counting those would report headers that are not
    set. Counting rather than parsing blocks keeps the test independent of how the file
    is arranged. What matters is that no header is declared fewer times than the
    others, which is exactly the shape of "forgot to repeat it in the location block".

    :return: Header name to number of declarations.
    """
    lines = [
        line
        for line in _NGINX_CONF.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    ]
    declared = re.findall(r"add_header\s+(\S+)", "\n".join(lines))
    return {header: declared.count(header) for header in _REQUIRED_HEADERS}


def _inline_script_sources() -> list[str]:
    """Return the exact text of every inline script in frontend/index.html.

    A script with a ``src`` attribute is loaded from 'self' and needs no hash.
    """
    html = _INDEX_HTML.read_text(encoding="utf-8")
    return re.findall(r"<script(?![^>]*\ssrc=)[^>]*>(.*?)</script>", html, re.DOTALL)


def _csp_hash(source: str) -> str:
    """Return the CSP source expression that allows exactly this script text."""
    digest = hashlib.sha256(source.encode("utf-8")).digest()
    return f"'sha256-{base64.b64encode(digest).decode()}'"


def _directive(csp: str, name: str) -> str:
    """Return a single directive out of a CSP header value."""
    for part in csp.split(";"):
        stripped = part.strip()
        if stripped.split(" ")[0] == name:
            return stripped
    raise AssertionError(f"CSP has no {name!r} directive: {csp}")


class TestNginxContentSecurityPolicy:
    """Tests for the CSP baked into the frontend image."""

    def test_declares_a_policy(self):
        """
        GIVEN the nginx config that serves the SPA
        WHEN its Content-Security-Policy headers are collected
        THEN at least one is declared
        """
        assert _csp_headers()

    @pytest.mark.parametrize("directive", _API_ORIGIN_DIRECTIVES)
    def test_directive_reaches_the_api_origin(self, directive: str):
        """
        GIVEN every Content-Security-Policy declared in nginx.conf
        WHEN the directives that must reach the API are read
        THEN each one carries the __API_ORIGIN__ placeholder

        A location block that sets any add_header of its own stops inheriting
        the server-level ones, so a copy that omits the placeholder would block
        API traffic for exactly the asset types that block serves.
        """
        for csp in _csp_headers():
            assert "__API_ORIGIN__" in _directive(csp, directive)

    @pytest.mark.parametrize("directive", _TURNSTILE_DIRECTIVES)
    def test_directive_allows_the_turnstile_widget(self, directive: str):
        """
        GIVEN every Content-Security-Policy declared in nginx.conf
        WHEN the directives the bot check depends on are read
        THEN each one names Cloudflare's Turnstile host

        Both failures are invisible and both lock every user out of the four auth
        forms. Without the host in script-src the browser blocks the widget's
        script, the loader promise rejects, no token is ever minted and submit
        stays disabled; without a frame-src the challenge iframe falls to
        default-src 'self' and is dropped just as quietly.
        """
        for csp in _csp_headers():
            assert _TURNSTILE_HOST in _directive(csp, directive)

    def test_inline_scripts_are_allowed_by_hash(self):
        """
        GIVEN the inline scripts in frontend/index.html
        WHEN each one is hashed
        THEN every copy of the policy lists that hash in script-src

        Without the hash the browser blocks the script silently, and dark-mode
        visitors get a white flash again while Czech visitors see English text
        first. The hash covers the exact text between the tags, so editing the
        script in any way makes this fail until nginx.conf is updated.
        """
        scripts = _inline_script_sources()
        assert scripts

        for csp in _csp_headers():
            script_src = _directive(csp, "script-src")
            for source in scripts:
                assert _csp_hash(source) in script_src.split()

    def test_script_src_carries_no_stale_hash(self):
        """
        GIVEN the inline scripts in frontend/index.html
        WHEN the sha256 sources in each copy of script-src are counted
        THEN there are exactly as many as there are inline scripts

        Editing the script adds the new hash; a hash left behind from the old text would
        keep allowing a script that no longer exists in the page.
        """
        expected = len(_inline_script_sources())

        for csp in _csp_headers():
            hashes = [
                source
                for source in _directive(csp, "script-src").split()
                if source.startswith("'sha256-")
            ]
            assert len(hashes) == expected

    def test_script_src_does_not_allow_unsafe_inline(self):
        """
        GIVEN every Content-Security-Policy declared in nginx.conf
        WHEN script-src is read
        THEN it does not contain 'unsafe-inline'

        The hash above is what lets the one inline script run. 'unsafe-inline'
        would let any injected script run too.
        """
        for csp in _csp_headers():
            assert "'unsafe-inline'" not in _directive(csp, "script-src")

    def test_placeholder_substitution_is_global(self):
        """
        GIVEN the Dockerfile that resolves __API_ORIGIN__ at build time
        WHEN its sed invocation is read
        THEN the substitution is global

        The placeholder now appears several times over. Without the /g flag sed
        would rewrite only the first, leaving a literal __API_ORIGIN__ in the
        served policy, which is why the build also greps for leftovers.
        """
        dockerfile = _DOCKERFILE.read_text(encoding="utf-8")

        assert "s#__API_ORIGIN__#${REPLACEMENT}#g" in dockerfile
        assert "! grep -q '__API_ORIGIN__' nginx.conf" in dockerfile


class TestNginxSecurityHeaders:
    """Every security header is repeated as often as the others.

    Same inheritance trap the CSP tests guard: a location block that sets any
    ``add_header`` stops inheriting the server-level ones, so a header declared once at
    the top silently disappears for whatever that block serves. The failure is quiet:
    the page still loads, just without the protection.
    """

    def test_each_required_header_is_declared(self):
        """
        GIVEN the nginx config that serves the SPA
        WHEN the required security headers are counted
        THEN none is missing entirely

        Referrer-Policy is on the list because the password-reset and activation pages
        carry a single-use token in the query string, and it is what keeps the full URL
        out of the Referer sent to any cross-origin destination.
        """
        counts = _header_counts()

        assert not [header for header, count in counts.items() if count == 0]

    def test_no_header_is_declared_fewer_times_than_the_others(self):
        """
        GIVEN the security headers the SPA sends
        WHEN their declaration counts are compared
        THEN they all match

        A header set in the server block but not repeated in the asset location block
        would show up here as a lower count, which is precisely the bug that shipped
        the SPA without a CSP once already.
        """
        counts = _header_counts()
        expected = max(counts.values())

        short = {header: count for header, count in counts.items() if count != expected}
        assert not short, f"declared fewer times than the other headers ({expected}): {short}"
