"""Tests for the frontend image's Cloudflare origin lock.

The API refuses a request without the Cloudflare origin secret (api/middleware/origin_lock.py),
and the SPA's nginx has to do the same, or a request sent straight to the Railway origin
skips Cloudflare and Cloudflare Access. frontend/nginx.conf answers 403 when ``$origin_allowed``
is 0, and frontend/docker-entrypoint.d/40-origin-lock.sh writes the maps that set it from the
container's environment at start, so the secret is never part of the image.

The static tests read the two files the way test_frontend_csp.py does. The behavioural tests
run the generator script with a temporary output path and read what it wrote. The last three
tests have nginx itself read the generated file and answer real requests, and are skipped
without a Docker daemon.
"""

import contextlib
import http.client
import os
import re
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from email.message import Message
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_NGINX_CONF = _PROJECT_ROOT / "frontend" / "nginx.conf"
_DOCKERFILE = _PROJECT_ROOT / "frontend" / "Dockerfile"
_SCRIPT = _PROJECT_ROOT / "frontend" / "docker-entrypoint.d" / "40-origin-lock.sh"

_SECRET = "Current-Secret_0123456789-abcdefghij"  # pragma: allowlist secret
_PREVIOUS = "Previous-Secret_9876543210-ABCDEFGHIJ"  # pragma: allowlist secret
_NGINX_IMAGE = "nginxinc/nginx-unprivileged:alpine"
# Secrets that start with "-" and "_", the two non-alphanumeric characters a value may hold.
_DASH_SECRET = "-aB3" * 10  # pragma: allowlist secret
_UNDERSCORE_SECRET = "_cD4" * 10  # pragma: allowlist secret

# A secret map key: an anchored regex in quotes, followed by the value 1.
_SECRET_KEY = re.compile(r'^"~\^([^"]*)\$"\s+1;$', re.MULTILINE)


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


def _map_lines(conf: str, variable: str) -> list[str]:
    """Return the stripped lines inside the map that sets ``variable``."""
    block = conf.split(f"{variable} {{", 1)[1].split("}", 1)[0]
    return [line.strip() for line in block.splitlines() if line.strip()]


def _secret_keys(conf: str) -> list[str]:
    """Return the values behind the ``$origin_secret_ok`` keys that map to 1."""
    return _SECRET_KEY.findall("\n".join(_map_lines(conf, "$origin_secret_ok")))


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
        GIVEN no CLOUDFLARE_ORIGIN_SECRET and no Railway environment
        WHEN the script runs
        THEN the secret map allows every request and the script succeeds
        """
        result, out = _run_script(tmp_path)

        conf = out.read_text(encoding="utf-8")
        assert result.returncode == 0
        assert _map_lines(conf, "$origin_secret_ok") == ["default 1;"]

    def test_secret_alone_is_the_only_key(self, tmp_path):
        """
        GIVEN a secret and an unset previous value
        WHEN the script runs
        THEN the secret is the one key mapped to 1, the default is 0, and no empty key exists

        An empty key would match a request that sends no header.
        """
        result, out = _run_script(tmp_path, CLOUDFLARE_ORIGIN_SECRET=_SECRET)

        conf = out.read_text(encoding="utf-8")
        assert result.returncode == 0
        assert _secret_keys(conf) == [_SECRET]
        assert _map_lines(conf, "$origin_secret_ok")[0] == "default 0;"
        assert '""' not in conf

    def test_keys_are_anchored_and_case_sensitive(self, tmp_path):
        """
        GIVEN a secret with upper and lower case letters
        WHEN the script runs
        THEN its key is the regex ~^value$, never the case-insensitive ~*

        nginx matches a plain map key without regard to case, which would accept the
        secret with its case changed.
        """
        _, out = _run_script(tmp_path, CLOUDFLARE_ORIGIN_SECRET=_SECRET)

        conf = out.read_text(encoding="utf-8")
        assert f'"~^{_SECRET}$" 1;' in conf
        assert "~*" not in conf

    def test_empty_previous_adds_no_key(self, tmp_path):
        """
        GIVEN a secret and a previous value set to an empty string
        WHEN the script runs
        THEN no second key is written
        """
        result, out = _run_script(
            tmp_path, CLOUDFLARE_ORIGIN_SECRET=_SECRET, CLOUDFLARE_ORIGIN_SECRET_PREVIOUS=""
        )

        assert result.returncode == 0
        assert _secret_keys(out.read_text(encoding="utf-8")) == [_SECRET]

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

    def test_the_deciding_maps_allow_by_default_and_refuse_both_failures(self, tmp_path):
        """
        GIVEN a secret
        WHEN the probe map and the $origin_allowed map are read
        THEN a request is refused only when it fails the secret and is not the probe,
            and the probe is GET on healthcheck.railway.app at /healthz and nothing else

        The two maps are what the 403 in nginx.conf reads, so a flipped default or key
        would open or close the whole site.
        """
        _, out = _run_script(tmp_path, CLOUDFLARE_ORIGIN_SECRET=_SECRET)

        conf = out.read_text(encoding="utf-8")
        assert _map_lines(conf, "$origin_probe") == [
            "default 0;",
            '"~^GET healthcheck\\.railway\\.app/healthz$" 1;',
        ]
        assert _map_lines(conf, "$origin_allowed") == ["default 1;", '"00" 0;']

    def test_the_maps_are_declared_over_the_right_inputs(self, tmp_path):
        """
        GIVEN a secret
        WHEN the generated file is read
        THEN the three maps are keyed on the header, the request line and the two results

        The map bodies are checked above, but a body is only as good as the variable its map
        reads, so a swapped input would pass them and open or close the whole site.
        """
        _, out = _run_script(tmp_path, CLOUDFLARE_ORIGIN_SECRET=_SECRET)

        lines = out.read_text(encoding="utf-8").splitlines()
        assert "map $http_x_origin_verify $origin_secret_ok {" in lines
        assert 'map "$request_method $host$request_uri" $origin_probe {' in lines
        assert 'map "$origin_secret_ok$origin_probe" $origin_allowed {' in lines

    @pytest.mark.parametrize("value", [_DASH_SECRET, _UNDERSCORE_SECRET])
    def test_a_value_may_start_with_a_dash_or_an_underscore(self, tmp_path, value):
        """
        GIVEN a secret that starts with "-" or "_", in either variable
        WHEN the script runs
        THEN it succeeds and both values are keys
        """
        other = _UNDERSCORE_SECRET if value == _DASH_SECRET else _DASH_SECRET

        result, out = _run_script(
            tmp_path,
            CLOUDFLARE_ORIGIN_SECRET=value,
            CLOUDFLARE_ORIGIN_SECRET_PREVIOUS=other,
        )

        assert result.returncode == 0
        assert _secret_keys(out.read_text(encoding="utf-8")) == [value, other]

    @pytest.mark.parametrize("length", [32, 128])
    def test_the_length_limits_are_inclusive(self, tmp_path, length):
        """
        GIVEN a secret of exactly the shortest or the longest accepted length
        WHEN the script runs
        THEN it succeeds and the value is a key
        """
        value = "a" * length

        result, out = _run_script(tmp_path, CLOUDFLARE_ORIGIN_SECRET=value)

        assert result.returncode == 0
        assert _secret_keys(out.read_text(encoding="utf-8")) == [value]

    @pytest.mark.parametrize(
        "name", ["CLOUDFLARE_ORIGIN_SECRET", "CLOUDFLARE_ORIGIN_SECRET_PREVIOUS"]
    )
    @pytest.mark.parametrize(
        "bad",
        [
            "~" + "a" * 40,
            "~*" + "a" * 40,
            "a" * 31,
            "a" * 129,
            "default",
            "include",
            "a" * 40 + '"',
            "a" * 40 + "\\",
            "a" * 40 + "$",
            "a" * 40 + ";",
            "a" * 40 + " b",
            "a" * 40 + "\nb",
            "a" * 40 + "\tb",
            "a" * 40 + "\u00e9",
            "a" * 40 + ".",
        ],
    )
    def test_unsafe_value_stops_the_script_and_writes_nothing(self, tmp_path, name, bad):
        """
        GIVEN a value outside A-Z, a-z, 0-9, _ and -, or shorter than 32 or longer than
            128 characters, in either variable
        WHEN the script runs
        THEN it exits 1, names the variable, writes no file and does not print the value
        """
        variables = {"CLOUDFLARE_ORIGIN_SECRET": _SECRET, name: bad}

        result, out = _run_script(tmp_path, **variables)

        assert result.returncode == 1
        assert name in result.stderr
        assert not out.exists()
        assert bad not in result.stdout + result.stderr

    def test_a_missing_secret_stops_the_script_on_railway(self, tmp_path):
        """
        GIVEN RAILWAY_ENVIRONMENT_NAME, which Railway sets on every deployment, and no secret
        WHEN the script runs
        THEN it exits 1 and writes no file, so the site never runs unlocked there
        """
        result, out = _run_script(tmp_path, RAILWAY_ENVIRONMENT_NAME="dev")

        assert result.returncode == 1
        assert "required on Railway" in result.stderr
        assert not out.exists()

    def test_a_secret_on_railway_is_accepted(self, tmp_path):
        """
        GIVEN RAILWAY_ENVIRONMENT_NAME and a valid secret
        WHEN the script runs
        THEN the lock is on
        """
        result, out = _run_script(
            tmp_path, RAILWAY_ENVIRONMENT_NAME="dev", CLOUDFLARE_ORIGIN_SECRET=_SECRET
        )

        assert result.returncode == 0
        assert _secret_keys(out.read_text(encoding="utf-8")) == [_SECRET]

    def test_a_previous_value_without_a_secret_stops_the_script(self, tmp_path):
        """
        GIVEN a previous value and no current secret
        WHEN the script runs
        THEN it exits 1 and writes no file, because a half-configured rotation must not
            open the site
        """
        result, out = _run_script(tmp_path, CLOUDFLARE_ORIGIN_SECRET_PREVIOUS=_PREVIOUS)

        assert result.returncode == 1
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


@pytest.fixture
def docker() -> str:
    """Return the docker executable, or skip the test when no Docker daemon answers."""
    path = shutil.which("docker")
    if path is None:
        pytest.skip("docker is not installed")
    info = subprocess.run([path, "info"], capture_output=True, check=False)  # noqa: S603
    if info.returncode != 0:
        pytest.skip("no Docker daemon is running")
    return path


class TestOriginLockInNginx:
    """nginx itself accepts the generated file next to the repository's config."""

    @pytest.mark.parametrize(
        "variables",
        [
            {},
            {"CLOUDFLARE_ORIGIN_SECRET": _SECRET},
            {"CLOUDFLARE_ORIGIN_SECRET": _SECRET, "CLOUDFLARE_ORIGIN_SECRET_PREVIOUS": _PREVIOUS},
        ],
    )
    def test_nginx_accepts_the_generated_maps(self, tmp_path, docker, variables):
        """
        GIVEN the file the script writes for no secret, a secret, and a secret with a previous one
        WHEN nginx -t reads it together with frontend/nginx.conf
        THEN the configuration test passes
        """
        _, out = _run_script(tmp_path, **variables)
        out.chmod(0o644)  # the nginx user in the container is not the file's owner

        result = subprocess.run(  # noqa: S603
            [
                docker,
                "run",
                "--rm",
                "-v",
                f"{out}:/etc/nginx/conf.d/00-origin-lock.conf:ro",
                "-v",
                f"{_NGINX_CONF}:/etc/nginx/conf.d/default.conf:ro",
                _NGINX_IMAGE,
                "nginx",
                "-t",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, result.stderr

    @pytest.mark.parametrize(
        ("secret", "previous"),
        [(_SECRET, _PREVIOUS), (_DASH_SECRET, _UNDERSCORE_SECRET)],
        ids=["plain", "dash-and-underscore"],
    )
    def test_nginx_answers_by_the_secret_and_the_probe(self, tmp_path, docker, secret, previous):
        """
        GIVEN nginx running with the generated maps and the repository's nginx.conf
        WHEN requests carry the current secret, the previous one, none, a wrong-case, longer or
            shorter secret, and when the probe host asks for /, for another path, for / with a
            query string, and for / by POST
        THEN the two secrets get 200, and everything else gets 403, the probe host's / included

        The second pair starts with "-" and "_", which nginx must read as part of a key.
        """
        _, conf = _run_script(
            tmp_path, CLOUDFLARE_ORIGIN_SECRET=secret, CLOUDFLARE_ORIGIN_SECRET_PREVIOUS=previous
        )
        probe = {"Host": "healthcheck.railway.app"}
        with _serving_nginx(docker, tmp_path, conf) as port:
            assert _status(port, "/", {"X-Origin-Verify": secret}) == 200
            assert _status(port, "/", {"X-Origin-Verify": previous}) == 200
            assert _status(port, "/") == 403
            assert _status(port, "/", {"X-Origin-Verify": secret.swapcase()}) == 403
            assert _status(port, "/", {"X-Origin-Verify": secret + "x"}) == 403
            assert _status(port, "/", {"X-Origin-Verify": secret[:-1]}) == 403
            assert _status(port, "/", probe) == 403
            assert _status(port, "/login", probe) == 403
            assert _status(port, "/?x=1", probe) == 403
            assert _status(port, "/", probe, method="POST") == 403

    def test_nginx_serves_the_health_path_to_the_probe_and_the_secret(self, tmp_path, docker):
        """
        GIVEN nginx running with the lock on and the repository's nginx.conf
        WHEN /healthz is requested by the probe host, with the secret, and by another host
            or with a wrong secret, and when the probe host asks for / and for another path
        THEN the probe host and the secret get 200 with an empty body, the others get 403,
            / is refused for the probe host like any other path, and the answer
            carries the server-level security headers once
        """
        _, conf = _run_script(tmp_path, CLOUDFLARE_ORIGIN_SECRET=_SECRET)
        probe = {"Host": "healthcheck.railway.app"}
        with _serving_nginx(docker, tmp_path, conf) as port:
            assert _response(port, "/healthz", probe)[:2] == (200, b"")
            assert _response(port, "/healthz", {"X-Origin-Verify": _SECRET})[:2] == (200, b"")
            assert _status(port, "/healthz") == 403
            assert _status(port, "/healthz", {"Host": "example.com"}) == 403
            assert _status(port, "/healthz", {"X-Origin-Verify": _SECRET.swapcase()}) == 403
            assert _status(port, "/healthz", probe, method="POST") == 403
            assert _status(port, "/", probe) == 403
            assert _status(port, "/healthz/", probe) == 403
            assert _status(port, "/HEALTHZ", probe) == 403
            assert _status(port, "/Healthz", probe) == 403
            headers = _response(port, "/healthz", probe)[2]
            assert len(headers.get_all("Content-Security-Policy")) == 1
            assert len(headers.get_all("X-Frame-Options")) == 1

    def test_nginx_without_a_secret_serves_every_request(self, tmp_path, docker):
        """
        GIVEN nginx running with the maps generated for an unset secret
        WHEN a request carries no X-Origin-Verify header
        THEN it gets 200, which is the unlocked mode of local development and CI
        """
        _, conf = _run_script(tmp_path)
        with _serving_nginx(docker, tmp_path, conf) as port:
            assert _status(port, "/") == 200


@contextlib.contextmanager
def _serving_nginx(docker: str, tmp_path: Path, conf: Path) -> Iterator[int]:
    """Run nginx with the generated maps and the repository's config, yield its port."""
    html = tmp_path / "html"
    html.mkdir()
    (html / "index.html").write_text("<!doctype html><title>ok</title>", encoding="utf-8")
    site = tmp_path / "default.conf"
    # The Dockerfile's sed fills this placeholder at build time. It only affects headers.
    site.write_text(
        _NGINX_CONF.read_text(encoding="utf-8").replace("__API_ORIGIN__", ""), encoding="utf-8"
    )
    for path in (conf, site):
        path.chmod(0o644)  # the nginx user in the container is not the file's owner
    html.chmod(0o755)
    (html / "index.html").chmod(0o644)
    port = _free_port()
    container = subprocess.run(  # noqa: S603
        [
            docker,
            "run",
            "-d",
            "--rm",
            "-p",
            f"127.0.0.1:{port}:8080",
            "-v",
            f"{conf}:/etc/nginx/conf.d/00-origin-lock.conf:ro",
            "-v",
            f"{site}:/etc/nginx/conf.d/default.conf:ro",
            "-v",
            f"{html}:/usr/share/nginx/html:ro",
            _NGINX_IMAGE,
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    try:
        if not _is_serving(port, {"Host": "healthcheck.railway.app"}):
            logs = subprocess.run(  # noqa: S603
                [docker, "logs", container], capture_output=True, text=True, check=False
            )
            pytest.fail(f"nginx did not answer on port {port}:\n{logs.stdout}{logs.stderr}")
        yield port
    finally:
        subprocess.run([docker, "rm", "-f", container], capture_output=True, check=False)  # noqa: S603


def _free_port() -> int:
    """Return a TCP port on the loopback interface that nothing is listening on."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _response(
    port: int, path: str, headers: dict[str, str] | None = None, method: str = "GET"
) -> tuple[int, bytes, Message]:
    """Return the status, body and headers of a request to the local nginx, errors included."""
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        headers={"User-Agent": "origin-lock-test", **(headers or {})},
        data=b"" if method == "POST" else None,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310
            return response.status, response.read(), response.headers
    except urllib.error.HTTPError as error:
        return error.code, error.read(), error.headers


def _status(
    port: int, path: str, headers: dict[str, str] | None = None, method: str = "GET"
) -> int:
    """Return the HTTP status of a request to the local nginx, error statuses included."""
    return _response(port, path, headers, method)[0]


def _is_serving(port: int, headers: dict[str, str], timeout: float = 30.0) -> bool:
    """Return True once nginx answers a request, False after ``timeout`` seconds."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            _status(port, "/", headers)
        except (OSError, http.client.HTTPException):
            time.sleep(0.2)
        else:
            return True
    return False
