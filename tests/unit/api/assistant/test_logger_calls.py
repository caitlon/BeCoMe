"""Static rules over every logger call of the assistant.

A log record of the assistant states what happened in a fixed message and puts the details in
``extra``. The message of a call is therefore always a string literal: an f-string, a
variable, a call, a concatenation or a ``%`` expression could carry a question, a name or a
model's text into the record. A traceback is the other way text reaches a record, because it
prints the message of the exception: so every ``exc_info=`` carries a comment that says why
that traceback is needed and what it holds.

This walks the syntax tree of ``api/assistant/`` and ``api/routes/assistant.py``, in the style
of ``tests/unit/api/test_logging_pii.py``, which does the same for the names of the ``extra``
fields. The behaviour of the running routes is pinned in
``tests/integration/api/test_assistant_logs.py``.
"""

import ast
import io
import tokenize
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
SCANNED = [
    *sorted((REPO_ROOT / "api" / "assistant").rglob("*.py")),
    REPO_ROOT / "api" / "routes" / "assistant.py",
]

# The methods of a logger that write a record. ``log`` takes the level first.
LOG_METHODS = frozenset(
    {"debug", "info", "warning", "warn", "error", "exception", "critical", "log"}
)
REASON_PREFIX = "# exc_info:"


def _receiver_is_a_logger(node: ast.expr) -> bool:
    """Say whether the object a method is called on is a logger.

    :param node: The expression before the dot: a name or attribute ending in ``logger`` or
        ``log`` (``logger``, ``security_logger``, ``self._logger``), the ``logging`` module,
        or a ``logging.getLogger(...)`` call.
    :return: True for any of those.
    """
    if isinstance(node, ast.Call):
        func = node.func
        return (isinstance(func, ast.Attribute) and func.attr == "getLogger") or (
            isinstance(func, ast.Name) and func.id == "getLogger"
        )
    name = node.id if isinstance(node, ast.Name) else getattr(node, "attr", "")
    return name == "logging" or name.endswith(("logger", "log"))


def _logger_calls(tree: ast.AST) -> list[ast.Call]:
    """Collect every call that writes a log record.

    :param tree: A parsed module.
    :return: The calls, in source order.
    """
    return sorted(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in LOG_METHODS
            and _receiver_is_a_logger(node.func.value)
        ),
        key=lambda call: (call.lineno, call.col_offset),
    )


def _message_of(call: ast.Call) -> ast.expr | None:
    """Return the expression a logger call uses as its message, or None when it has none.

    :param call: A logger call. ``log`` takes the level first, so its message is the second
        argument; any other method takes it first. ``msg=`` is read as the message too.
    :return: The message expression.
    """
    assert isinstance(call.func, ast.Attribute)
    index = 1 if call.func.attr == "log" else 0
    if len(call.args) > index:
        return call.args[index]
    return next((keyword.value for keyword in call.keywords if keyword.arg == "msg"), None)


def logger_call_count(path: Path) -> int:
    """Count the logger calls in one module.

    :param path: Module to scan.
    :return: The number of calls.
    """
    return len(_logger_calls(ast.parse(path.read_text(encoding="utf-8"), filename=str(path))))


def message_violations(path: Path) -> list[tuple[int, str]]:
    """Find the logger calls whose message is not a string literal.

    :param path: Module to scan.
    :return: ``(line number, what the message is)`` for each such call.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[int, str]] = []
    for call in _logger_calls(tree):
        message = _message_of(call)
        if message is None:
            found.append((call.lineno, "no message"))
        elif not (isinstance(message, ast.Constant) and isinstance(message.value, str)):
            found.append((call.lineno, type(message).__name__))
    return found


def _comments(source: str) -> dict[int, tuple[str, bool]]:
    """Read the comments of a module by line.

    :param source: The module's text.
    :return: For each line with a comment, the comment and whether it is alone on its line.
    """
    found: dict[int, tuple[str, bool]] = {}
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            alone = token.line[: token.start[1]].strip() == ""
            found[token.start[0]] = (token.string, alone)
    return found


def _has_reason(comments: dict[int, tuple[str, bool]], line: int) -> bool:
    """Say whether the keyword on ``line`` has a reason comment.

    The comment is at the end of the keyword's own line, or it is a block of comment lines
    that ends on the line above and starts with ``# exc_info:``, followed by some text.

    :param comments: The module's comments, from :func:`_comments`.
    :param line: The line of the ``exc_info=`` keyword.
    :return: True when the reason is there.
    """
    same_line = comments.get(line)
    if same_line is not None and same_line[0].startswith(REASON_PREFIX):
        return bool(same_line[0].removeprefix(REASON_PREFIX).strip())
    first = line - 1
    if first not in comments or not comments[first][1]:
        return False
    while first - 1 in comments and comments[first - 1][1]:
        first -= 1
    opening = comments[first][0]
    return opening.startswith(REASON_PREFIX) and bool(opening.removeprefix(REASON_PREFIX).strip())


def exc_info_lines(path: Path) -> list[int]:
    """Find every ``exc_info=`` keyword of a module.

    :param path: Module to scan.
    :return: Their line numbers.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return sorted(
        keyword.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        for keyword in node.keywords
        if keyword.arg == "exc_info"
    )


def reason_violations(path: Path) -> list[int]:
    """Find the ``exc_info=`` keywords that carry no reason comment.

    :param path: Module to scan.
    :return: The line numbers of those keywords.
    """
    comments = _comments(path.read_text(encoding="utf-8"))
    return [line for line in exc_info_lines(path) if not _has_reason(comments, line)]


def _module_ids(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


@pytest.mark.parametrize("module", SCANNED, ids=_module_ids)
def test_every_logger_call_has_a_literal_message(module):
    """
    GIVEN a module of the assistant
    WHEN the message of each of its logger calls is read
    THEN every message is a string literal, so no text of a question, a name or a model's
        answer can be built into it
    """
    # GIVEN/WHEN
    offenders = message_violations(module)

    # THEN
    assert not offenders, (
        f"{_module_ids(module)} writes a log message that is not a string literal: {offenders}. "
        "Write a fixed message and put the details in extra={...}; %s may take a type name."
    )


@pytest.mark.parametrize("module", SCANNED, ids=_module_ids)
def test_every_exc_info_has_a_reason_comment(module):
    """
    GIVEN a module of the assistant
    WHEN each exc_info= keyword is looked up
    THEN a comment starting with '# exc_info:' and some text stands on its line or directly
        above it, so a reviewer reads why that traceback may be written
    """
    # GIVEN/WHEN
    offenders = reason_violations(module)

    # THEN
    assert not offenders, (
        f"{_module_ids(module)} has exc_info= without a '# exc_info: <reason>' comment "
        f"on lines {offenders}. The traceback prints the exception's message: say why that "
        "is needed and why it holds no user text."
    )


def test_the_scan_reaches_the_real_calls():
    """
    GIVEN the files the rules scan
    WHEN their logger calls and exc_info keywords are counted
    THEN more than 25 calls and at least one keyword are found, and the files include the
        route module, so the parametrised tests above cannot pass on an empty scan
    """
    # GIVEN/WHEN
    calls = sum(logger_call_count(module) for module in SCANNED)
    keywords = sum(len(exc_info_lines(module)) for module in SCANNED)

    # THEN
    assert calls > 25
    assert keywords > 0
    assert REPO_ROOT / "api" / "routes" / "assistant.py" in SCANNED
    assert REPO_ROOT / "api" / "assistant" / "deps.py" in SCANNED


_CLEAN_MODULE = """
import logging

logger = logging.getLogger(__name__)
security_logger = logging.getLogger("api.security")


def work(exc, level):
    logger.info("Assistant turn finished", extra={"event": "assistant_turn"})
    logger.warning("Assistant failed: %s", type(exc).__name__, extra={"event": "failed"})
    logger.log(level, "%s -> %d", type(exc).__name__, 500)
    logging.getLogger("api.x").error("Fixed text", extra={"event": "x"})
    security_logger.warning(
        "Refund failed",
        extra={"event": "refund_failed"},
        exc_info=True,  # exc_info: names the failing store command, never user text
    )
    logger.error(
        "Store down",
        # exc_info: a Redis error names the failing command and the store's address,
        # never a key or a message.
        exc_info=exc,
    )
    message = f"not a logger call {exc}"
    print(f"{message}")
    notes.append(f"{message}")
    logger.isEnabledFor(10)
"""


def test_a_clean_module_passes_both_rules(tmp_path):
    """
    GIVEN a module whose logger calls take literal messages (with %s arguments, a level
        first for log, and a getLogger call), whose exc_info keywords carry a reason on
        their own line or in the block above, and which formats text in calls that are
        not loggers
    WHEN both rules read it
    THEN neither finds anything, and the scan did find the calls and the keywords
    """
    # GIVEN
    module = tmp_path / "clean.py"
    module.write_text(_CLEAN_MODULE, encoding="utf-8")

    # WHEN/THEN
    assert logger_call_count(module) == 6
    assert len(exc_info_lines(module)) == 2
    assert message_violations(module) == []
    assert reason_violations(module) == []


@pytest.mark.parametrize(
    ("call", "kind"),
    [
        ('logger.warning(f"Asked {question}")', "JoinedStr"),
        ("logger.info(message)", "Name"),
        ("logger.info(build_message())", "Call"),
        ('logger.error("Failed: " + detail)', "BinOp"),
        ('logger.error("Failed: %s" % detail)', "BinOp"),
        ('logger.error("Failed: {}".format(detail))', "Call"),
        ('security_logger.warning(f"{question}")', "JoinedStr"),
        ('self._logger.debug(f"{question}")', "JoinedStr"),
        ("logger.log(logging.ERROR, message)", "Name"),
        ('logger.exception(f"{question}")', "JoinedStr"),
        ("logger.warn(message)", "Name"),
        ('logging.getLogger("x").info(message)', "Name"),
        ('logging.info(f"{question}")', "JoinedStr"),
        ("logger.info(msg=message)", "Name"),
        ("logger.info()", "no message"),
    ],
)
def test_a_message_that_is_not_a_literal_is_found(tmp_path, call, kind):
    """
    GIVEN a module with one logger call whose message is built or held in a variable
    WHEN the literal-message rule reads it
    THEN it reports that call and the kind of expression the message is
    """
    # GIVEN
    module = tmp_path / "planted.py"
    module.write_text(f"def work():\n    {call}\n", encoding="utf-8")

    # WHEN
    found = message_violations(module)

    # THEN
    assert found == [(2, kind)]


@pytest.mark.parametrize(
    "keyword_line",
    [
        "exc_info=True,",
        "exc_info=True,  # because the traceback helps",
        "exc_info=True,  # exc_info:",
        "exc_info=True,  # exc_info:    ",
    ],
)
def test_exc_info_without_a_reason_is_found(tmp_path, keyword_line):
    """
    GIVEN a logger call with exc_info= that has no comment, an unrelated one, or the prefix
        with no reason after it
    WHEN the reason rule reads the module
    THEN it reports the line of the keyword
    """
    # GIVEN
    module = tmp_path / "planted.py"
    module.write_text(
        f'def work():\n    logger.error(\n        "Failed",\n        {keyword_line}\n    )\n',
        encoding="utf-8",
    )

    # WHEN
    found = reason_violations(module)

    # THEN
    assert found == [4]


def test_a_reason_two_lines_above_or_on_a_code_line_does_not_count(tmp_path):
    """
    GIVEN an exc_info= whose reason comment is separated from it by a code line, and one
        whose comment above trails a code line instead of standing alone
    WHEN the reason rule reads the module
    THEN both keywords are reported
    """
    # GIVEN
    module = tmp_path / "planted.py"
    module.write_text(
        "def work():\n"
        "    # exc_info: a reason that is too far away\n"
        "    logger.error(\n"
        '        "Failed",\n'
        "        exc_info=True,\n"
        "    )\n"
        "    logger.error(\n"
        '        "Failed",  # exc_info: this trails a code line\n'
        "        exc_info=True,\n"
        "    )\n",
        encoding="utf-8",
    )

    # WHEN
    found = reason_violations(module)

    # THEN
    assert found == [5, 9]
