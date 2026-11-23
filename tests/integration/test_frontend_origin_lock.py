"""Tests for the frontend image's Cloudflare origin lock.

The API refuses a request without the Cloudflare origin secret (api/middleware/origin_lock.py),
and the SPA's nginx has to do the same, or a request sent straight to the Railway origin
skips Cloudflare and Cloudflare Access. frontend/nginx.conf answers 403 when ``$origin_allowed``
is 0, and frontend/docker-entrypoint.d/40-origin-lock.sh writes the maps that set it from the
container's environment at start, so the secret is never part of the image.

The static tests read the two files the way test_frontend_csp.py does. The behavioural tests
run the generator script with a temporary output path and read what it wrote.
"""

import os
import re
import subprocess
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_NGINX_CONF = _PROJECT_ROOT / "frontend" / "nginx.conf"
_DOCKERFILE = _PROJECT_ROOT / "frontend" / "Dockerfile"
_SCRIPT = _PROJECT_ROOT / "frontend" / "docker-entrypoint.d" / "40-origin-lock.sh"

_SECRET = "current-secret-0123456789"  # pragma: allowlist secret
_PREVIOUS = "previous-secret-9876543210"  # pragma: allowlist secret

# A map key: a quoted string followed by the value 1.
_ALLOWED_KEY = re.compile(r'^\s+"([^"]*)"\s+1;', re.MULTILINE)


def _run_script(tmp_path: Path, **variables: str) -> tuple[subprocess.CompletedProcess, Path]:
    """Run the generator with an output path in ``tmp_path`` and the given variables.

    :param tmp_path: Directory the script writes into.
    :param variables: Environment variables to set, on top of an otherwise empty one.
    :return: The finished process and the path the script was told to write.
    """
    out = tmp_path / "00-origin-lock.conf"
    env = {"PATH": os.environ["PATH"], "ORIGIN_LOCK_CONF": str(out), **variables}
    result = subprocess.run(  # noqa: S603
        ["/bin/sh", str(_SCRIPT)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return result, out


def _secret_keys(conf: str) -> list[str]:
    """Return the quoted keys of the ``$origin_secret_ok`` map that map to 1."""
    block = conf.split("$origin_secret_ok {", 1)[1].split("}", 1)[0]
    return _ALLOWED_KEY.findall(block)


class TestOriginLockWiring:
    """nginx.conf refuses, and the image ships the script that feeds it."""

    def test_nginx_conf_answers_403_when_the_origin_is_not_allowed(self):
        """
        GIVEN the nginx config that serves the SPA
        WHEN its server block is read
        THEN it returns 403 when $origin_allowed is 0, and adds no header of its own for it

        An add_header in the server block is counted by test_frontend_csp.py, and one in
        a location would stop that location inheriting the security headers.
        """
        conf = _NGINX_CONF.read_text(encoding="utf-8")

        assert re.search(r"if \(\$origin_allowed = 0\) \{\s*return 403;\s*\}", conf)

    def test_dockerfile_ships_the_script_executable(self):
        """
        GIVEN frontend/Dockerfile
        WHEN its final stage is read
        THEN the script is copied into /docker-entrypoint.d/ with the executable bit

        The base image skips a script there that is not executable, with one log line,
        and the site then runs unlocked.
        """
        dockerfile = _DOCKERFILE.read_text(encoding="utf-8")

        assert (
            "COPY --chmod=0755 docker-entrypoint.d/40-origin-lock.sh "
            "/docker-entrypoint.d/40-origin-lock.sh"
        ) in dockerfile
        assert os.access(_SCRIPT, os.X_OK)

    def test_the_secret_is_not_baked_into_the_image(self):
        """
        GIVEN frontend/Dockerfile
        WHEN it is searched for the secret's variable names
        THEN neither is an ARG or an ENV

        Both come from the container's runtime environment.
        """
        dockerfile = _DOCKERFILE.read_text(encoding="utf-8")

        assert not re.search(r"^\s*(ARG|ENV)\s+CLOUDFLARE_", dockerfile, re.MULTILINE)


class TestOriginLockGenerator:
    """The script turns the environment into the nginx maps."""

    def test_unset_secret_switches_the_check_off(self, tmp_path):
        """
        GIVEN no CLOUDFLARE_ORIGIN_SECRET
        WHEN the script runs
        THEN the secret map allows every request and the script succeeds
        """
        result, out = _run_script(tmp_path)

        conf = out.read_text(encoding="utf-8")
        assert result.returncode == 0
        assert _secret_keys(conf) == []
        assert "default 1;" in conf.split("$origin_secret_ok {", 1)[1].split("}", 1)[0]

    def test_empty_secret_switches_the_check_off(self, tmp_path):
        """
        GIVEN CLOUDFLARE_ORIGIN_SECRET set to an empty string and a previous value
        WHEN the script runs
        THEN the check is off, as for an unset one
        """
        result, out = _run_script(
            tmp_path, CLOUDFLARE_ORIGIN_SECRET="", CLOUDFLARE_ORIGIN_SECRET_PREVIOUS=_PREVIOUS
        )

        conf = out.read_text(encoding="utf-8")
        assert result.returncode == 0
        assert _secret_keys(conf) == []
        assert _PREVIOUS not in conf

    def test_secret_alone_is_the_only_key(self, tmp_path):
        """
        GIVEN a secret and an unset previous value
        WHEN the script runs
        THEN the secret is the one key mapped to 1 and the default is 0

        An empty key would match a request that sends no header.
        """
        result, out = _run_script(tmp_path, CLOUDFLARE_ORIGIN_SECRET=_SECRET)

        conf = out.read_text(encoding="utf-8")
        block = conf.split("$origin_secret_ok {", 1)[1].split("}", 1)[0]
        assert result.returncode == 0
        assert _secret_keys(conf) == [_SECRET]
        assert "default 0;" in block
        assert '""' not in conf

    def test_empty_previous_adds_no_key(self, tmp_path):
        """
        GIVEN a secret and a previous value set to an empty string
        WHEN the script runs
        THEN no empty key is written
        """
        result, out = _run_script(
            tmp_path, CLOUDFLARE_ORIGIN_SECRET=_SECRET, CLOUDFLARE_ORIGIN_SECRET_PREVIOUS=""
        )

        conf = out.read_text(encoding="utf-8")
        assert result.returncode == 0
        assert _secret_keys(conf) == [_SECRET]
        assert '""' not in conf

    def test_both_values_are_keys(self, tmp_path):
        """
        GIVEN a secret and a previous value
        WHEN the script runs
        THEN both are keys mapped to 1
        """
        result, out = _run_script(
            tmp_path,
            CLOUDFLARE_ORIGIN_SECRET=_SECRET,
            CLOUDFLARE_ORIGIN_SECRET_PREVIOUS=_PREVIOUS,
        )

        assert result.returncode == 0
        assert _secret_keys(out.read_text(encoding="utf-8")) == [_SECRET, _PREVIOUS]

    def test_equal_values_make_one_key(self, tmp_path):
        """
        GIVEN a previous value equal to the secret
        WHEN the script runs
        THEN the key is written once, because nginx refuses a repeated map key
        """
        result, out = _run_script(
            tmp_path,
            CLOUDFLARE_ORIGIN_SECRET=_SECRET,
            CLOUDFLARE_ORIGIN_SECRET_PREVIOUS=_SECRET,
        )

        assert result.returncode == 0
        assert _secret_keys(out.read_text(encoding="utf-8")) == [_SECRET]

    def test_only_the_railway_probe_of_the_root_is_exempt(self, tmp_path):
        """
        GIVEN a secret
        WHEN the generated probe map is read
        THEN its one key is GET on healthcheck.railway.app at /
        """
        _, out = _run_script(tmp_path, CLOUDFLARE_ORIGIN_SECRET=_SECRET)

        block = out.read_text(encoding="utf-8").split("$origin_probe {", 1)[1].split("}", 1)[0]
        assert _ALLOWED_KEY.findall(block) == ["GET healthcheck.railway.app/"]

    @pytest.mark.parametrize(
        "bad",
        ['ab"cd', "ab\\cd", "ab$cd", "ab;cd", "ab cd", "ab\ncd", "ab\tcd", "abc\u00e9", "a" * 129],
    )
    def test_unsafe_secret_stops_the_script_and_writes_nothing(self, tmp_path, bad):
        """
        GIVEN a secret with a character that would break a quoted nginx string, or one
            that is too long for the map
        WHEN the script runs
        THEN it exits non-zero, writes no file and does not print the value
        """
        result, out = _run_script(tmp_path, CLOUDFLARE_ORIGIN_SECRET=bad)

        assert result.returncode != 0
        assert not out.exists()
        assert bad not in result.stdout + result.stderr

    def test_unsafe_previous_value_stops_the_script_too(self, tmp_path):
        """
        GIVEN a valid secret and a previous value with a quote in it
        WHEN the script runs
        THEN it exits non-zero and writes no file
        """
        result, out = _run_script(
            tmp_path, CLOUDFLARE_ORIGIN_SECRET=_SECRET, CLOUDFLARE_ORIGIN_SECRET_PREVIOUS='a"b'
        )

        assert result.returncode != 0
        assert not out.exists()

    def test_the_secret_is_never_printed(self, tmp_path):
        """
        GIVEN a secret and a previous value
        WHEN the script runs
        THEN neither appears in its output, and the file is readable by its owner alone
        """
        result, out = _run_script(
            tmp_path,
            CLOUDFLARE_ORIGIN_SECRET=_SECRET,
            CLOUDFLARE_ORIGIN_SECRET_PREVIOUS=_PREVIOUS,
        )

        output = result.stdout + result.stderr
        assert _SECRET not in output
        assert _PREVIOUS not in output
        assert out.stat().st_mode & 0o777 == 0o600
