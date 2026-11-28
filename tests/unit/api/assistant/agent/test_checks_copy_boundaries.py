"""Tests for a verbatim copy of a name that a bare URL or a link target runs into."""

import pytest

from api.assistant.agent import service as service_module
from api.assistant.agent.checks import find_ungrounded_numbers
from tests.unit.api.assistant.agent.test_service import _ctx

_B = "Budget 2027"
_GAPS = {"newline": "\n", "tab": "\t", "three-spaces": "   ", "space-newline-space": " \n "}


def _case(name, answer, copies, expected, kept=()):
    """Build a row: the answer is checked with the copies and the kept copies given."""
    return pytest.param(answer, copies, kept, expected, id=name)


# fmt: off
_CASES = [
    # The plain scan ends a URL at the copy's first space, so what follows the copy is read.
    _case("url-ends-inside-the-copy", "See https://x.y/Budget 2027;99999 now.", (_B,), ["99999"]),
    _case("url-ends-at-the-copy-and-nothing-follows", "See https://x.y/Budget 2027 now.", (_B,), []),
    _case("link-target-with-a-space-is-a-url", "See [x](https://x.y/Budget 2027)99999 now.", (_B,), ["99999"]),
    _case("link-target-url-ends-inside-the-copy", "See [x](https://x.y/Budget 2027;99999) now.", (_B,), ["99999"]),
    _case("lowercase-copy-in-a-url", "See https://x.y/pilot 2027;5 now.", ("pilot 2027",), ["5"]),
    _case("lowercase-copy-in-a-url-at-the-end", "https://x.y/pilot 2027;5", ("pilot 2027",), ["5"]),
    # Every copy of a run ends the URL it is in, and what follows the last one is read.
    _case("two-urls-each-ending-in-a-copy",
          "See https://x.y/Budget 2027;https://x.y/Plan 2028;99999 now.", (_B, "Plan 2028"), ["99999"]),
    _case("two-copies-in-one-url-run",
          "See https://x.y/Budget 2027;Plan 2028;99999 now.", (_B, "Plan 2028"), ["99999"]),
    # A copy that starts with a URL is dropped whole, and the text after it is read.
    _case("copy-starting-with-a-url", "See https://x.y/a b 2027;77 now.", ("https://x.y/a b 2027",), ["77"]),
    # A copy without whitespace ends no URL: the URL goes on past it, and swallows what follows.
    _case("one-word-copy-inside-a-url", "See https://x.y/Jana/reports/2024 now.", ("Jana",), []),
    _case("one-word-copy-ends-the-url", "See https://x.y/Jana;2024 now.", ("Jana",), []),
    # A link target stops at a space and at a bracket, so a copy that holds either ends it where
    # the plain scan ends it, and a copy without both leaves it whole.
    _case("link-target-ends-inside-the-copy", "[x](Budget 7;7)", ("Budget 7",), ["7"]),
    _case("link-target-ends-at-the-copy", "[x](Budget 7)7", ("Budget 7",), ["7"]),
    _case("link-target-and-nothing-follows", "[x](Budget 7)", ("Budget 7",), []),
    _case("one-word-copy-inside-a-link-target", "[x](Jana;7)", ("Jana",), []),
    _case("bracketed-copy-inside-a-link-target", "[x](Plan(2027);2027)", ("Plan(2027)",), ["2027"]),
    _case("bracketed-copy-with-a-space-in-a-link-target", "[x](Plan (2027);2027)", ("Plan (2027)",), ["2027"]),
    _case("bracketed-copy-alone-in-a-link-target", "[x](Plan(2027))", ("Plan(2027)",), []),
    _case("bracketed-copy-in-running-text", "See (Plan(2027)) now.", ("Plan(2027)",), []),
    _case("square-bracketed-copy-inside-a-link-target", "[x](Plan[2027];2027)", ("Plan[2027]",), ["2027"]),
    _case("bracket-inside-a-copy-in-a-link-target", "[x](Plan [2027];2027)", ("Plan [2027]",), ["2027"]),
    _case("copy-as-link-text", "[Plan 2027](https://x.y/a)", ("Plan 2027",), []),
    # A copy that starts with a URL keeps its scheme, so what is glued to it stays in the URL.
    _case("url-copy-glued-to-a-bracket", "See https://x.y/z[ 7] now.", ("https://x.y/z",), ["7"]),
    _case("url-copy-glued-to-a-parenthesis", "See https://x.y/z(77) now.", ("https://x.y/z",), []),
    # A scheme inside a copy is kept as well, so a URL that starts there runs on past the copy.
    _case("url-starts-inside-the-copy-and-swallows-a-parenthesis", "see https://x.y/z(77) now", ("see https://x.y/z",), []),
    _case("url-ends-the-copy-and-swallows-a-bracket", "Jana http://[ 7] gave.", ("Jana http://",), ["7"]),
    # Any run of whitespace in the copy ends a URL, as the first whitespace of the plain scan.
    *[_case(f"url-ends-at-a-{name}-inside-the-copy", f"See https://x.y/Budget{gap}2027;99999 now.", (_B,), ["99999"])
      for name, gap in _GAPS.items()],
    *[_case(f"url-copy-with-a-{name}-inside", f"See https://x.y/a{gap}b 2027;8", ("https://x.y/a b 2027",), ["8"])
      for name, gap in _GAPS.items()],
    # A kept copy stays as written, so the scan reads it as it reads the plain text.
    _case("kept-copy-in-a-url", "See https://x.y/Budget 2027;99999 now.", (), ["2027", "99999"], kept=(_B,)),
    _case("copy-shadowed-by-a-longer-kept-one", "See https://x.y/Budget 2027 plan;99999 now.", (_B,),
          ["2027", "99999"], kept=("Budget 2027 plan",)),
]
# fmt: on


class TestUrlsAndCopies:
    """A copy a bare URL or a link target runs into does not change where that URL ends."""

    @pytest.mark.parametrize(("answer", "copies", "kept", "expected"), _CASES)
    def test_the_url_ends_where_the_plain_scan_ends_it(self, answer, copies, kept, expected):
        """
        GIVEN an answer with a bare URL or a link target that runs into a copy of a name (the
              table above: a copy that holds a space or a bracket, one that does not, lowercase,
              two in a run, one that starts with a URL, a kept one)
        WHEN it is checked with the copy
        THEN the numbers that the plain scan reads outside the copy are reported, and none that
             the copy holds
        """
        assert find_ungrounded_numbers(answer, [], copies=list(copies), kept=list(kept)) == expected


def _sorted_out(answer, *, project=(), expert=()):
    """Run the number check of a turn that was shown the given project and expert names."""
    ctx = _ctx()
    ctx.project_name_copies = list(project)
    ctx.expert_name_copies = list(expert)
    checked = service_module._check_numbers(answer, [], ctx)
    return checked.ungrounded, checked.project_name, checked.expert_name


_STATED = [
    pytest.param(
        "See https://x.y/Budget 2027;2027 now.", _B, "2027", id="url-ends-inside-the-name"
    ),
    pytest.param("http://x 42=42", "x 42", "42", id="url-glued-to-the-name-by-an-equals-sign"),
    pytest.param("[N](https://x.y/Budget 42)42", "Budget 42", "42", id="url-in-a-link-target"),
    pytest.param("[x](Budget 7;7)", "Budget 7", "7", id="link-target-ends-inside-the-name"),
    pytest.param("[x](Budget 7)7", "Budget 7", "7", id="link-target-ends-at-the-name"),
    pytest.param(
        "[x](Plan(2027);2027)", "Plan(2027)", "2027", id="link-target-with-a-bracketed-name"
    ),
    pytest.param(
        "See https://x.y/z[ 7] and Plan 7.",
        ("https://x.y/z", "Plan 7"),
        "7",
        id="url-name-glued-to-a-bracket",
    ),
    pytest.param("Jana http://[ 7] gave.", "Jana http://", "7", id="url-scheme-ends-the-name"),
    pytest.param(
        "Jana http://[ 7] gave. Plan 7 is open.",
        ("Jana http://", "Plan 7"),
        "7",
        id="url-scheme-ends-the-name-beside-a-name-with-the-number",
    ),
]


class TestNumbersStatedAfterAUrlName:
    """A number stated after a URL or link target that a name copy ends is the model's."""

    @pytest.mark.parametrize(("answer", "name", "number"), _STATED)
    @pytest.mark.parametrize("kind", ["project", "expert"])
    def test_the_number_stays_ungrounded(self, answer, name, number, kind):
        """
        GIVEN a name (or two) shown to the model that holds a number and sits inside a bare URL
              or a link target (one that the name ends, with the number stated right after it),
              as a project's or an expert's name
        WHEN the answer is checked
        THEN the stated number is ungrounded, and neither name list holds it
        """
        names = {kind: [name] if isinstance(name, str) else list(name)}

        assert _sorted_out(answer, **names) == ([number], [], [])
