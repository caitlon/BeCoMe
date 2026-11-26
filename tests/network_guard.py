"""Refuse every socket operation that would leave the machine during a test run.

Installed by the root ``tests/conftest.py`` before anything imports ``api``, so it
covers collection, fixtures and every xdist worker. Loopback addresses, the unspecified
addresses (``0.0.0.0`` and ``::``, which connect to this machine), unix sockets, bind
and listen stay allowed: the assistant tests start HTTP stubs on ``127.0.0.1``, asyncio
uses a socket pair for its self-pipe and pytest-postgresql talks to its server over a unix
socket. This machine's own host name is not allowed, because resolving it goes to the
system resolver and can send a real DNS or reverse query: ``socket.getfqdn()`` and
``email.utils.make_msgid()`` are refused, and a test that needs them mocks them.
Everything else is refused with :class:`NetworkBlockedError` and recorded, because several
clients (the MX check, Sentry, LangSmith, the Better Stack handler) swallow their own
errors, so a refusal alone can pass unnoticed.

When ``NETWORK_GUARD_LOG`` names a file, every refused attempt is appended to it as one
JSON line with the test id, the operation and the target.
"""

from __future__ import annotations

import contextlib
import ipaddress
import json
import os
import socket
from collections.abc import Iterable
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

LOG_ENV = "NETWORK_GUARD_LOG"

# The only names every resolver answers locally (RFC 6761); others may go to DNS.
_LOOPBACK_NAMES = frozenset({"localhost", "localhost."})
_INET_FAMILIES = frozenset({socket.AF_INET, socket.AF_INET6})
# Set on the socket module by install(), so a second copy of this module loaded under
# another name leaves the first one's patches (and its attempts list) in charge.
_INSTALLED_MARK = "_become_network_guard"

_real: dict[str, Any] = {
    "connect": socket.socket.connect,
    "connect_ex": socket.socket.connect_ex,
    "sendto": socket.socket.sendto,
    "sendmsg": socket.socket.sendmsg,
    "getaddrinfo": socket.getaddrinfo,
    "gethostbyname": socket.gethostbyname,
    "gethostbyname_ex": socket.gethostbyname_ex,
    "gethostbyaddr": socket.gethostbyaddr,
    "getnameinfo": socket.getnameinfo,
}

attempts: list[dict[str, Any]] = []


class NetworkBlockedError(RuntimeError):
    """Raised when a test reaches for a host other than this machine."""


def is_loopback_host(host: object) -> bool:
    """Tell whether a host name or address stays on this machine.

    :param host: Host as passed to a socket call: ``str``, ``bytes`` or ``None``.
    :return: True for ``None`` and the empty string (a passive lookup), ``localhost`` and
        ``localhost.``, and any address in ``127.0.0.0/8``, ``::1``, ``0.0.0.0`` or ``::``,
        IPv4-mapped included (Python 3.13 judges the embedded IPv4 address itself). Nothing is
        trimmed, because the value goes to the real resolver as it is, so ``" localhost "``
        and ``"[::1]"`` are not local; a URL drops its own brackets before it asks. An
        IPv6 ``%scope`` suffix is read by :mod:`ipaddress`; on a name it is part of the name.
    """
    if host is None:
        return True
    if isinstance(host, bytes):
        host = host.decode("ascii", errors="replace")
    if not isinstance(host, str):
        return False
    name = host.lower()
    if name == "" or name in _LOOPBACK_NAMES:
        return True
    try:
        address = ipaddress.ip_address(name)
    except ValueError:
        return False
    return address.is_loopback or address.is_unspecified


def _first_remote(hosts: Iterable[str]) -> str | None:
    """Return the first host that is not this machine; a ``/`` prefix is a local socket directory."""
    for host in hosts:
        if not host.startswith("/") and not is_loopback_host(host):
            return host
    return None


def remote_database_host(url: str) -> str | None:
    """Find a database host in a URL that is not this machine.

    libpq takes hosts from the authority (one or several, comma-separated, percent-encoded)
    and from the ``host`` and ``hostaddr`` query parameters. A value starting with ``/`` is
    a unix socket directory, and an empty one means the default local socket. A ``service``
    parameter names a service file that cannot be read here, so it counts as remote. The
    environment fallbacks are in :func:`remote_libpq_environment`.

    :param url: A database URL; an empty one and ``sqlite`` URLs have no host.
    :return: The first host outside this machine (``service=<name>`` for a service), or
        None when every host is local. Only the host is returned, never the URL, which
        carries a password.
    """
    if not url or url.startswith("sqlite"):
        return None
    parts = urlsplit(url)
    hosts = []
    for item in parts.netloc.rpartition("@")[2].split(","):
        hosts.append(
            unquote(item[1 : item.find("]")] if item.startswith("[") else item.partition(":")[0])
        )
    query = parse_qs(parts.query)
    for key in ("host", "hostaddr"):
        for value in query.get(key, []):
            hosts.extend(value.split(","))
    if host := _first_remote(hosts):
        return host
    return f"service={query['service'][0]}" if "service" in query else None


def remote_libpq_environment() -> tuple[str, str] | None:
    """Find a libpq environment variable that points a database connection off this machine.

    libpq reads these whatever the URL says: ``PGHOST`` and ``PGHOSTADDR`` fill in a missing
    host, and ``PGSERVICE`` names a service file that cannot be read here.

    :return: The variable and its host (``service=<name>`` for ``PGSERVICE``), or None.
    """
    if service := os.environ.get("PGSERVICE"):
        return "PGSERVICE", f"service={service}"
    for name in ("PGHOST", "PGHOSTADDR"):
        if host := _first_remote(os.environ.get(name, "").split(",")):
            return name, host
    return None


def _refuse(operation: str, host: object, port: object = None) -> None:
    if isinstance(host, bytes):
        host = host.decode("ascii", errors="replace")
    target = f"{host}:{port}" if port is not None else str(host)
    record = {
        "test": os.environ.get("PYTEST_CURRENT_TEST", "<outside a test>"),
        "operation": operation,
        "target": target,
        "pid": os.getpid(),
    }
    attempts.append(record)
    log_path = os.environ.get(LOG_ENV)
    if log_path:
        # A bad log path must not replace the refusal below.
        with contextlib.suppress(OSError), open(log_path, "a", encoding="utf-8") as log:
            log.write(json.dumps(record) + "\n")
    raise NetworkBlockedError(
        f"network access is blocked in tests: {operation} to {target}. "
        "Mock the client, or use a stub server on 127.0.0.1 (tests/README.md)."
    )


def _check_address(sock: socket.socket, operation: str, address: object) -> None:
    if sock.family not in _INET_FAMILIES:
        return
    if not isinstance(address, tuple) or not address:
        return
    host = address[0]
    port = address[1] if len(address) > 1 else None
    if not is_loopback_host(host):
        _refuse(operation, host, port)


def _connect(self: socket.socket, address: Any) -> None:
    _check_address(self, "connect", address)
    _real["connect"](self, address)


def _connect_ex(self: socket.socket, address: Any) -> int:
    _check_address(self, "connect", address)
    return int(_real["connect_ex"](self, address))


def _sendto(self: socket.socket, data: Any, *args: Any) -> int:
    _check_address(self, "sendto", args[-1] if args else None)
    return int(_real["sendto"](self, data, *args))


def _sendmsg(self: socket.socket, buffers: Any, *args: Any) -> int:
    if len(args) >= 3:
        _check_address(self, "sendmsg", args[2])
    return int(_real["sendmsg"](self, buffers, *args))


def _guarded_lookup(name: str, operation: str) -> Any:
    """Build the guarded version of one lookup function of the socket module.

    :param name: Attribute of ``socket`` to wrap; its first argument is the host.
    :param operation: How a refusal is recorded: ``name lookup`` or ``reverse lookup``.
    :return: A function that refuses a host outside this machine, else calls the original.
    """

    def guarded(host: Any, *args: Any, **kwargs: Any) -> Any:
        if not is_loopback_host(host):
            _refuse(operation, host)
        return _real[name](host, *args, **kwargs)

    guarded.__name__ = name
    return guarded


def _getnameinfo(sockaddr: Any, flags: int) -> Any:
    if isinstance(sockaddr, tuple) and sockaddr and not is_loopback_host(sockaddr[0]):
        _refuse("reverse lookup", sockaddr[0])
    return _real["getnameinfo"](sockaddr, flags)


_GUARDED_LOOKUPS = {
    "getaddrinfo": "name lookup",
    "gethostbyname": "name lookup",
    "gethostbyname_ex": "name lookup",
    "gethostbyaddr": "reverse lookup",
}


def install() -> None:
    """Patch the socket module; calling it again, from any copy of this module, is a no-op."""
    if getattr(socket, _INSTALLED_MARK, False):
        return
    setattr(socket, _INSTALLED_MARK, True)
    socket.socket.connect = _connect  # type: ignore[method-assign,assignment]
    socket.socket.connect_ex = _connect_ex  # type: ignore[method-assign,assignment]
    socket.socket.sendto = _sendto  # type: ignore[method-assign,assignment]
    socket.socket.sendmsg = _sendmsg  # type: ignore[method-assign,assignment]
    for name, operation in _GUARDED_LOOKUPS.items():
        setattr(socket, name, _guarded_lookup(name, operation))
    socket.getnameinfo = _getnameinfo
