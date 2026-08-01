"""Regression tests for the SPA's Content-Security-Policy.

frontend/nginx.conf serves the React SPA and carries its CSP. The API is a
separate origin on every deploy (https://api.<domain>), so any directive that
has to reach the API names the placeholder __API_ORIGIN__, which
frontend/Dockerfile substitutes with the real origin at image build time.

Two directives need it, for different reasons: connect-src covers fetch/XHR,
and img-src covers profile photos, which the API serves as image bytes
(GET /users/{id}/photo) rendered in <img> tags. Missing img-src is a silent
failure -- the browser drops the request before it leaves the tab, so nothing
appears in the API logs and the avatar simply never renders. That shipped to
production once; these tests exist so it cannot ship again.

The config is plain text with no runtime the test suite can exercise, so this
module parses it, the same way test_frontend_case_studies.py parses
caseStudies.ts.
"""

import re
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_NGINX_CONF = _PROJECT_ROOT / "frontend" / "nginx.conf"
_DOCKERFILE = _PROJECT_ROOT / "frontend" / "Dockerfile"

_CSP_HEADER = re.compile(r'add_header\s+Content-Security-Policy\s+"([^"]*)"')

# Directives that must reach the API origin. nginx repeats the whole header in
# every location block that sets one of its own, so each copy is checked.
_API_ORIGIN_DIRECTIVES = ("connect-src", "img-src")


def _csp_headers() -> list[str]:
    """Return every Content-Security-Policy value declared in nginx.conf."""
    return _CSP_HEADER.findall(_NGINX_CONF.read_text(encoding="utf-8"))


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

    def test_placeholder_substitution_is_global(self):
        """
        GIVEN the Dockerfile that resolves __API_ORIGIN__ at build time
        WHEN its sed invocation is read
        THEN the substitution is global

        The placeholder now appears several times over. Without the /g flag sed
        would rewrite only the first, leaving a literal __API_ORIGIN__ in the
        served policy -- which is why the build also greps for leftovers.
        """
        dockerfile = _DOCKERFILE.read_text(encoding="utf-8")

        assert "s#__API_ORIGIN__#${REPLACEMENT}#g" in dockerfile
        assert "! grep -q '__API_ORIGIN__' nginx.conf" in dockerfile
