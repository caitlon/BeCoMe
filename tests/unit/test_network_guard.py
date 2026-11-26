"""Tests for the socket guard that keeps the suite on this machine."""

import email.utils
import importlib.util
import json
import re
import socket
from collections.abc import Callable, Iterator
from functools import partial
from typing import Any

import pytest

from tests import conftest, network_guard
from tests.network_guard import NetworkBlockedError, is_loopback_host, remote_database_host

pytest_plugins = ["pytester"]

# A made-up remote database URL whose password must never reach a message.
_REMOTE_URL_WITH_PASSWORD = (
    "postgresql://user:hunter2@db.example.com/prod"  # pragma: allowlist secret
)

# TEST-NET-1 (RFC 5737) and the IPv6 documentation prefix (RFC 3849): never routed.
_OUT = "192.0.2.1"
_OUT_V6 = "2001:db8::1"

_FIXTURE_CONFTEST = "from tests.conftest import _no_swallowed_network_attempt  # noqa: F401\n"
_SESSION_CONFTEST = (
    "from tests.conftest import _no_swallowed_network_attempt, pytest_sessionfinish  # noqa: F401\n"
)
_INNER_ARGS = ("-p", "no:cacheprovider", "-o", "asyncio_default_fixture_loop_scope=function")
_TCP = (socket.AF_INET, socket.SOCK_STREAM)
_TCP6 = (socket.AF_INET6, socket.SOCK_STREAM)
_UDP = (socket.AF_INET, socket.SOCK_DGRAM)


@pytest.fixture(autouse=True)
def _forget_deliberate_attempts(monkeypatch) -> Iterator[None]:
    """Remove the refusals these tests cause, so the root check sees only real leaks.

    The root fixture is set up before this one and torn down after it, so it compares the
    list after this fixture has cut it back. The log file is off for the same reason.

    :yield: Control to the test.
    """
    monkeypatch.delenv(network_guard.LOG_ENV, raising=False)
    seen = len(network_guard.attempts)
    yield
    del network_guard.attempts[seen:]


def _on_socket(kind: tuple[int, int], method: str, *args: Any) -> Any:
    """Call ``method`` on a new socket with a one second timeout, skipping if it cannot exist."""
    try:
        sock = socket.socket(*kind)
    except OSError:
        pytest.skip("this host cannot open that kind of socket")
    with sock:
        sock.settimeout(1)
        return getattr(sock, method)(*args)


_tcp, _udp = partial(_on_socket, _TCP), partial(_on_socket, _UDP)
_NAME = ("name lookup", "example.com")
# Label, the call to make, the operation the guard records and the target it names.
_REFUSALS = [
    ("connect", partial(_tcp, "connect", (_OUT, 443)), "connect", f"{_OUT}:443"),
    ("connect_ex", partial(_tcp, "connect_ex", (_OUT, 443)), "connect", f"{_OUT}:443"),
    (
        "connect-v6",
        partial(_on_socket, _TCP6, "connect", (_OUT_V6, 80)),
        "connect",
        f"{_OUT_V6}:80",
    ),
    ("sendto", partial(_udp, "sendto", b"ping", (_OUT, 9)), "sendto", f"{_OUT}:9"),
    ("sendmsg", partial(_udp, "sendmsg", [b"ping"], [], 0, (_OUT, 9)), "sendmsg", f"{_OUT}:9"),
    ("getaddrinfo", partial(socket.getaddrinfo, "example.com", 443), *_NAME),
    ("gethostbyname", partial(socket.gethostbyname, "example.com"), *_NAME),
    ("gethostbyname_ex", partial(socket.gethostbyname_ex, "example.com"), *_NAME),
    ("gethostbyaddr", partial(socket.gethostbyaddr, _OUT), "reverse lookup", _OUT),
    ("getnameinfo", partial(socket.getnameinfo, (_OUT, 53), 0), "reverse lookup", _OUT),
    (
        "bytes-host",
        partial(socket.getaddrinfo, b"api.resend.com", 443),
        "name lookup",
        "api.resend.com",
    ),
]

_LOOPBACK = ["localhost", "localhost.", "localhost.localdomain", "ip6-localhost", "ip6-loopback"]
_LOOPBACK += ["127.0.0.1", "127.8.9.10", "::1", "::1%lo0"]
_UNSPECIFIED = ["0.0.0.0", "::", "::ffff:0.0.0.0"]  # noqa: S104 - the values under test
_LOCAL_HOSTS = [None, "", b"localhost", "[::1]", "::ffff:127.0.0.1", *_LOOPBACK, *_UNSPECIFIED]
_OUTSIDE_HOSTS = ["example.com", "10.0.0.1", _OUT, "::ffff:10.0.0.1", "fe80::1%en0"]
_OUTSIDE_HOSTS += ["localhost.example.com", "localhost%.example.com"]
_SOCKET_DIR = "/tmp"  # noqa: S108 - a unix socket directory, never created


def _run(pytester, conftest: str, source: str, *args: str) -> Any:
    pytester.makeconftest(conftest)
    pytester.makepyfile(source)
    return pytester.runpytest_inprocess(*_INNER_ARGS, *args)


# An xdist worker reports a failed run to its controller through session.shouldfail.
_SHOW_SHOULDFAIL = """
def pytest_sessionfinish(session):
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    reporter.write_line("SHOULDFAIL=" + str(session.shouldfail))
"""


class TestRefusedConnections:
    """Anything that is not this machine is refused, and the refusal is recorded."""

    @pytest.mark.parametrize(
        ("call", "operation", "target"),
        [row[1:] for row in _REFUSALS],
        ids=[row[0] for row in _REFUSALS],
    )
    def test_an_operation_that_leaves_the_machine_is_refused_and_recorded(
        self, call: Callable[[], Any], operation: str, target: str
    ):
        """GIVEN a call aimed outside, WHEN it runs, THEN it raises and records the target as text."""
        with pytest.raises(NetworkBlockedError, match=re.escape(target)) as refused:
            call()

        assert "b'" not in str(refused.value)
        assert network_guard.attempts[-1]["operation"] == operation
        assert network_guard.attempts[-1]["target"] == target

    def test_a_refusal_is_appended_to_the_log_file_when_one_is_named(self, monkeypatch, tmp_path):
        """GIVEN NETWORK_GUARD_LOG, WHEN a connect is refused, THEN the file gets one JSON line."""
        log = tmp_path / "guard.jsonl"
        monkeypatch.setenv(network_guard.LOG_ENV, str(log))

        with pytest.raises(NetworkBlockedError):
            _on_socket(_TCP, "connect", (_OUT, 443))

        record = json.loads(log.read_text(encoding="utf-8"))
        assert (record["operation"], record["target"]) == ("connect", f"{_OUT}:443")
        assert "test_a_refusal_is_appended_to_the_log_file" in record["test"]

    def test_the_machines_own_name_is_not_looked_up(self, monkeypatch):
        """GIVEN a non-loopback host name, WHEN getfqdn or make_msgid asks, THEN both are refused."""
        monkeypatch.setattr(socket, "gethostname", lambda: "my-laptop.example")

        with pytest.raises(NetworkBlockedError, match=r"my-laptop\.example"):
            socket.getfqdn()
        with pytest.raises(NetworkBlockedError, match=r"my-laptop\.example"):
            email.utils.make_msgid()

        assert network_guard.attempts[-1]["operation"] == "reverse lookup"


class TestAllowedTraffic:
    """This machine stays reachable: loopback, local servers and unix sockets."""

    def test_connect_to_a_closed_loopback_port_fails_the_ordinary_way(self):
        """GIVEN nothing on 127.0.0.1:1, WHEN a socket connects, THEN the OS refuses it, not the guard."""
        before = len(network_guard.attempts)

        with pytest.raises(ConnectionRefusedError):
            _on_socket(_TCP, "connect", ("127.0.0.1", 1))

        assert len(network_guard.attempts) == before

    def test_a_local_server_accepts_a_loopback_client(self):
        """GIVEN a listening loopback server, WHEN a client connects, THEN it reads the line sent."""
        with socket.socket(*_TCP) as server:
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            with socket.create_connection(server.getsockname(), timeout=2) as client:
                client.sendall(b"hello")
                connection, _ = server.accept()
                with connection:
                    connection.settimeout(2)
                    received = connection.recv(5)

        assert received == b"hello"

    def test_lookups_of_this_machine_go_through(self):
        """GIVEN localhost and 127.0.0.1, WHEN they are looked up, THEN the resolver answers."""
        flags = socket.NI_NUMERICHOST | socket.NI_NUMERICSERV

        assert socket.getaddrinfo("localhost", 80)
        assert socket.getnameinfo(("127.0.0.1", 80), flags) == ("127.0.0.1", "80")

    def test_udp_between_loopback_sockets_is_allowed(self):
        """GIVEN a UDP socket on 127.0.0.1, WHEN another sends to it, THEN the datagram arrives."""
        with socket.socket(*_UDP) as receiver, socket.socket(*_UDP) as sender:
            receiver.bind(("127.0.0.1", 0))
            receiver.settimeout(2)
            sender.sendto(b"ping", receiver.getsockname())
            data, _ = receiver.recvfrom(16)

        assert data == b"ping"

    def test_a_unix_socket_pair_is_allowed(self):
        """GIVEN a unix socket pair, WHEN one sends bytes, THEN the other receives them."""
        left, right = socket.socketpair()
        with left, right:
            left.sendall(b"ping")
            assert right.recv(4) == b"ping"


class TestIsLoopbackHost:
    """Which host spellings count as this machine."""

    @pytest.mark.parametrize(
        ("host", "expected"),
        [(host, True) for host in _LOCAL_HOSTS] + [(host, False) for host in _OUTSIDE_HOSTS],
    )
    def test_names_and_addresses_are_judged_by_where_they_lead(self, host, expected):
        """GIVEN a spelling of a host, WHEN it is checked, THEN it is loopback only if it leads here."""
        assert is_loopback_host(host) is expected

    def test_this_machines_own_host_name_is_not_a_local_name(self):
        """GIVEN this machine's host name, WHEN it is checked, THEN it is not loopback."""
        name = socket.gethostname()
        if is_loopback_host(name):
            pytest.skip("this machine is named after a loopback name")

        assert is_loopback_host(name) is False


class TestRemoteDatabaseHost:
    """A database URL that leaves the machine is found, whichever way it names the host."""

    @pytest.mark.parametrize(
        ("url", "env", "expected"),
        [
            # Local, or never connecting.
            ("", {}, None),
            ("sqlite://", {}, None),
            ("sqlite:///./local.db", {}, None),
            ("postgresql://u:p@localhost/db", {}, None),
            ("postgresql://u:p@127.0.0.1:5432/db", {}, None),
            ("postgresql://u:p@[::1]:5432/db", {}, None),
            ("postgresql:///db", {}, None),
            (f"postgresql:///db?host={_SOCKET_DIR}", {}, None),
            ("postgresql://localhost,127.0.0.1/db", {}, None),
            ("postgresql:///db?host=localhost&hostaddr=127.0.0.1", {}, None),
            # Remote: the host is reported, never the URL.
            ("postgresql://u:p@db.example.com/db", {}, "db.example.com"),
            ("postgresql+psycopg://u:p@db.example.com:5432/db", {}, "db.example.com"),
            ("postgresql://u:p@[2001:db8::1]:5432/db", {}, "2001:db8::1"),
            ("postgresql:///db?host=remote.example", {}, "remote.example"),
            ("postgresql://u:p@localhost/db?hostaddr=192.0.2.1", {}, "192.0.2.1"),
            ("postgresql://u:p@localhost,db.example.com/db", {}, "db.example.com"),
            ("postgresql:///db?host=localhost,remote.example", {}, "remote.example"),
            # No host in the URL: libpq falls back to its environment.
            ("postgresql:///db", {"PGHOST": "db.example.com"}, "db.example.com"),
            ("postgresql:///db", {"PGHOST": "localhost,db.example.com"}, "db.example.com"),
            ("postgresql:///db", {"PGHOSTADDR": _OUT}, _OUT),
            ("postgresql:///db", {"PGSERVICE": "production"}, "service=production"),
            ("postgresql:///db", {"PGHOST": _SOCKET_DIR}, None),
            ("postgresql:///db", {"PGHOST": "localhost"}, None),
            ("postgresql:///db", {"PGHOSTADDR": "127.0.0.1"}, None),
            # A host in the URL, or no connection at all, makes the environment irrelevant.
            ("postgresql://u:p@localhost/db", {"PGHOST": "db.example.com"}, None),
            (f"postgresql:///db?host={_SOCKET_DIR}", {"PGHOST": "db.example.com"}, None),
            ("sqlite://", {"PGHOST": "db.example.com"}, None),
            ("", {"PGSERVICE": "production"}, None),
        ],
    )
    def test_the_host_outside_this_machine_is_reported_alone(self, monkeypatch, url, env, expected):
        """GIVEN a database URL and a libpq environment, WHEN checked, THEN only a remote host is returned."""
        for name in ("PGHOST", "PGHOSTADDR", "PGSERVICE"):
            monkeypatch.delenv(name, raising=False)
        for name, value in env.items():
            monkeypatch.setenv(name, value)

        assert remote_database_host(url) == expected


class TestInstall:
    """The guard installs once, however many copies of the module get loaded."""

    def test_a_second_copy_of_the_module_leaves_the_installed_guard_recording(self):
        """GIVEN a second copy of the module, WHEN it installs, THEN refusals land in the first copy."""
        spec = importlib.util.spec_from_file_location("guard_copy", network_guard.__file__)
        assert spec is not None and spec.loader is not None
        copy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(copy)

        copy.install()
        with pytest.raises(NetworkBlockedError):
            _on_socket(_TCP, "connect", (_OUT, 443))

        assert network_guard.attempts[-1]["target"] == f"{_OUT}:443"
        assert copy.attempts == []


class TestDatabaseUrlPin:
    """The root conftest refuses a database URL that leaves the machine, before any test runs."""

    @pytest.mark.parametrize(
        "name", ["DATABASE_URL", "MIGRATION_DATABASE_URL", "ASSISTANT_VECTOR_DB_URL"]
    )
    def test_a_remote_database_url_stops_the_run_and_names_only_its_host(self, monkeypatch, name):
        """GIVEN a remote URL with a password, WHEN the pin runs, THEN it raises with the host only."""
        monkeypatch.setattr(conftest, "read_test_env", dict)
        monkeypatch.setenv(name, _REMOTE_URL_WITH_PASSWORD)

        with pytest.raises(RuntimeError) as refused:
            conftest._pin_environment()

        assert (
            str(refused.value)
            == f"{name} must point at this machine in tests, not 'db.example.com'"
        )


class TestSwallowedRefusal:
    """A client that catches the guard's error still fails its test."""

    @pytest.mark.parametrize(
        ("statement", "reported"),
        [
            (f"socket.create_connection(({_OUT!r}, 443), timeout=1)", "name lookup to 192.0.2.1"),
            (f"socket.socket().connect(({_OUT!r}, 443))", "connect to 192.0.2.1:443"),
        ],
    )
    def test_a_test_that_swallows_a_refusal_is_reported_as_an_error(
        self, pytester, statement, reported
    ):
        """GIVEN a test that catches the guard's error, WHEN it runs, THEN it errors at teardown."""
        source = f"""
            import socket

            def test_swallows_the_refusal():
                try:
                    {statement}
                except Exception:
                    pass
            """

        result = _run(pytester, _FIXTURE_CONFTEST, source)

        result.assert_outcomes(passed=1, errors=1)
        result.stdout.fnmatch_lines([f"*tried to leave the machine: {reported}*"])
        assert "first recorded under" not in result.stdout.str()

    def test_an_attempt_recorded_under_another_test_names_that_test(self, pytester):
        """GIVEN an attempt recorded by an earlier test, WHEN it lands later, THEN the label names it."""
        source = """
            from tests import network_guard

            def test_a_late_attempt_lands_here():
                earlier = "test_earlier.py::test_started_a_thread (call)"
                network_guard.attempts.append(
                    dict(test=earlier, operation="connect", target="192.0.2.1:443", pid=1)
                )
            """

        result = _run(pytester, _FIXTURE_CONFTEST, source)

        result.assert_outcomes(passed=1, errors=1)
        result.stdout.fnmatch_lines(
            ["*connect to 192.0.2.1:443 (first recorded under test_earlier.py::test_started_a_*"]
        )


class TestRefusalOutsideATest:
    """A refusal that no test reported fails the run when the session ends."""

    def test_a_refusal_swallowed_in_a_module_fixture_fails_the_run(self, pytester):
        """GIVEN a module fixture that swallows a refusal, WHEN the test passes, THEN the run fails."""
        source = f"""
            import socket

            import pytest

            @pytest.fixture(scope="module")
            def client():
                try:
                    with socket.socket() as sock:
                        sock.settimeout(1)
                        sock.connect(({_OUT!r}, 443))
                except Exception:
                    pass

            def test_passes(client):
                pass
            """

        pytester.makepyfile(showfail=_SHOW_SHOULDFAIL)
        pytester.syspathinsert()

        result = _run(pytester, _SESSION_CONFTEST, source, "-p", "showfail")

        message = f"the run tried to leave the machine outside a test: connect to {_OUT}:443"
        result.assert_outcomes(passed=1)
        assert result.ret == pytest.ExitCode.TESTS_FAILED
        result.stdout.fnmatch_lines([f"*{message}*", f"SHOULDFAIL={message}"])

    def test_a_refusal_a_test_already_reported_is_not_reported_again(self, pytester):
        """GIVEN a refusal a test reported, WHEN the session ends, THEN the run-level report is silent."""
        source = f"""
            import socket

            def test_swallows_the_refusal():
                try:
                    socket.socket().connect(({_OUT!r}, 443))
                except Exception:
                    pass
            """

        result = _run(pytester, _SESSION_CONFTEST, source)

        result.assert_outcomes(passed=1, errors=1)
        assert "outside a test" not in result.stdout.str()
