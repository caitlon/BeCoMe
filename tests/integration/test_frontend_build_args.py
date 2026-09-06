"""Regression test for the frontend image's build arguments.

Vite inlines ``import.meta.env.VITE_*`` at build time, so a variable that is absent
from the builder's environment when ``npm run build`` runs collapses to undefined in
the bundle. Railway passes a service variable to the image as a build argument, and
a build argument reaches that environment only through an ``ARG`` in
frontend/Dockerfile. A variable missing from that file is therefore one that is set
on every service and present in no build.

That has now happened twice. ``VITE_SENTRY_DSN`` was set on all three services while
none of the deployed bundles ever initialised Sentry, and ``VITE_TURNSTILE_SITE_KEY``
shipped the same way: no sitekey means no widget, no token on the request, and an API
running the bot check refuses every auth request with a 403. Neither failure shows up
in a build log, so this test reads the two files against each other instead.
"""

import re
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DOCKERFILE = _PROJECT_ROOT / "frontend" / "Dockerfile"
_SOURCE_ROOT = _PROJECT_ROOT / "frontend" / "src"

# Only the VITE_ prefix is injectable. Vite's own DEV/PROD/MODE come from the build
# mode rather than the environment, so they are no one's build argument.
_ENV_READ = re.compile(r"import\.meta\.env\.(VITE_[A-Z0-9_]+)")
_BUILD_ARG = re.compile(r"^\s*ARG\s+(VITE_[A-Z0-9_]+)", re.MULTILINE)


def _variables_read_by_the_spa() -> set[str]:
    """Return every VITE_ variable the SPA's source reads.

    :return: Variable names, without the values they are compared against.
    """
    return {
        name
        for path in _SOURCE_ROOT.rglob("*.ts*")
        for name in _ENV_READ.findall(path.read_text(encoding="utf-8"))
    }


class TestFrontendBuildArgs:
    """The image is built with every variable the bundle expects to have."""

    def test_every_variable_the_spa_reads_is_declared_as_a_build_arg(self):
        """
        GIVEN every VITE_ variable the SPA's source reads
        WHEN the build arguments frontend/Dockerfile declares are read
        THEN none of those variables is missing from them

        An undeclared one does not fail the build, fail the deploy, or warn: the
        image is served, and whatever the variable was meant to switch on is
        simply never on.
        """
        missing = _variables_read_by_the_spa() - set(
            _BUILD_ARG.findall(_DOCKERFILE.read_text(encoding="utf-8"))
        )

        assert not missing, f"read by the SPA, never declared as ARG: {sorted(missing)}"
