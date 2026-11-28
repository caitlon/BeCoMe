"""A loopback Redis server stub that answers like a read-only replica.

redis-py rewrites the message of an error raised inside a pipeline, and only a real
connection to a server that refuses the commands shows what that message says. This stub
speaks just enough of the wire protocol (RESP) for redis-py's handshake and for the
commands the application sends. It listens on ``127.0.0.1`` only, on a port the system
picks, so a test that uses it reaches nothing beyond this machine.

By default every write command is refused with ``READONLY``, ``MULTI`` and ``WATCH`` are
accepted, ``EXEC`` is refused with ``EXECABORT`` (a transaction whose queued commands were
refused), and reads answer as an empty store. A test overrides the replies to any command with
:meth:`RespStub.reply_to`, one reply per call of that command, in order.
"""

import io
import socket
import socketserver
import threading
from collections.abc import Iterator
from contextlib import contextmanager, suppress

_READONLY_REPLY = b"-READONLY You can't write against a read only replica.\r\n"
_EXECABORT_REPLY = b"-EXECABORT Transaction discarded because of previous errors.\r\n"
_OK_REPLY = b"+OK\r\n"
_NULL_REPLY = b"_\r\n"
# RESP3 map ``{"proto": 3}``: what redis-py's ``HELLO 3`` handshake needs to see.
_HELLO_REPLY = b"%1\r\n$5\r\nproto\r\n:3\r\n"

# redis-py sends ``INCR`` and ``DECR`` as ``INCRBY`` and ``DECRBY``.
_WRITES = frozenset({"SET", "INCRBY", "DECRBY", "EXPIRE", "DEL", "EVAL", "EVALSHA", "SETEX"})
_ACCEPTED = frozenset({"MULTI", "WATCH", "UNWATCH", "DISCARD"})
_READS = {"GET": _NULL_REPLY, "TTL": b":-2\r\n", "EXISTS": b":0\r\n"}


def _read_command(stream: io.BufferedIOBase) -> list[bytes] | None:
    """Read one command, an array of bulk strings, from the stream.

    :param stream: The connection's read side.
    :return: The command's words, or None when the client closed the connection.
    """
    header = stream.readline()
    if not header.startswith(b"*"):
        return None
    words: list[bytes] = []
    for _ in range(int(header[1:])):
        size = int(stream.readline()[1:])
        words.append(stream.read(size))
        stream.read(2)
    return words


class _Handler(socketserver.StreamRequestHandler):
    """Serve one client connection until it closes."""

    server: "_Server"

    def handle(self) -> None:
        """Answer each command with the reply the stub holds for it."""
        self.server.connections.append(self.request)
        while True:
            try:
                words = _read_command(self.rfile)
            except (OSError, ValueError):
                return
            if words is None:
                return
            self.server.commands.append(words)
            try:
                self.wfile.write(self.server.reply_for(words))
                self.wfile.flush()
            except OSError:
                return


class _Server(socketserver.ThreadingTCPServer):
    """The listening socket, with the commands it received and the replies it holds."""

    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, replies: dict[str, list[bytes]]) -> None:
        super().__init__(("127.0.0.1", 0), _Handler)
        self.replies = replies
        self._calls: dict[str, int] = {}
        self._lock = threading.Lock()
        self.commands: list[list[bytes]] = []
        self.connections: list[socket.socket] = []

    def reset_calls(self, name: str) -> None:
        """Start counting the calls of one command again.

        :param name: The command name in upper case.
        """
        with self._lock:
            self._calls.pop(name, None)

    def reply_for(self, words: list[bytes]) -> bytes:
        """Return the reply to one command.

        :param words: The command's words.
        :return: The raw reply bytes.
        """
        name = words[0].decode().upper()
        if name in self.replies:
            with self._lock:
                call = self._calls.get(name, 0)
                self._calls[name] = call + 1
            scripted = self.replies[name]
            return scripted[min(call, len(scripted) - 1)]
        if name == "HELLO":
            return _HELLO_REPLY
        if name == "EXEC":
            return _EXECABORT_REPLY
        if name in _WRITES:
            return _READONLY_REPLY
        if name in _ACCEPTED:
            return _OK_REPLY
        if name in _READS:
            return _READS[name]
        if name == "CLIENT":
            return _OK_REPLY
        return b"-ERR unknown command\r\n"


class RespStub:
    """A running stub server, as a test sees it.

    :ivar url: The ``redis://`` URL of the stub, on ``127.0.0.1``.
    """

    def __init__(self, server: _Server) -> None:
        self._server = server
        self.url = f"redis://127.0.0.1:{server.server_address[1]}/0"

    def reply_to(self, command: str, *replies: bytes) -> None:
        """Set the raw replies the stub gives to one command from now on.

        The first call of the command gets the first reply, the second call the second, and
        every later call the last one. Calls made before this one are not counted.

        :param command: The command name, for example ``TTL``.
        :param replies: The replies in the wire protocol, for example ``b"-ERR boom\\r\\n"``.
        """
        name = command.upper()
        self._server.replies[name] = list(replies)
        self._server.reset_calls(name)

    def received(self, text: str) -> bool:
        """Say whether any command received so far carries ``text`` in one of its words.

        :param text: What to look for, for example a key.
        :return: True when a command held it.
        """
        return any(text in word.decode() for words in list(self._server.commands) for word in words)


@contextmanager
def resp_stub(replies: dict[str, list[bytes]] | None = None) -> Iterator[RespStub]:
    """Run a read-only replica stub on a loopback port for the length of a ``with`` block.

    The connections the clients opened are closed on the way out, so no handler thread is
    left waiting.

    :param replies: Raw replies by command name, replacing the defaults; see
        :meth:`RespStub.reply_to`.
    :return: The running stub.
    """
    server = _Server({name.upper(): reply for name, reply in (replies or {}).items()})
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield RespStub(server)
    finally:
        server.shutdown()
        for connection in server.connections:
            with suppress(OSError):
                connection.shutdown(socket.SHUT_RDWR)
        server.server_close()
        thread.join(timeout=5)
