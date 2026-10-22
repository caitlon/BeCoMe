"""Who took part in an assistant turn, and how their names and positions are hidden.

A :class:`TurnRoster` collects the experts of every opinions list the turn fetched and
gives each one a label, ``Expert 1``, ``Expert 2`` and so on, in order of first
appearance. :func:`mask_participants` then replaces, in any text, what names a participant
with that label, and what names a participant's position with ``[position of Expert 1]``.
The labels are the ones the opinions block carries (see
:func:`~api.assistant.agent.tools.render_opinions`), so a trace and the block agree on who
is who.

The match is built to over-mask rather than to miss. A name is found as the whole name and
as each of its words, in the Czech cases a word takes (Nováková, Novákové, Novákovou),
with or without diacritics (Novak). The whole name, and any word of it of five letters or
more, is found in any case of its first letter, so "co řekl jan novák" is masked. A shorter
word keeps the case it was written in, so ``Will`` is found and the verb ``will`` is not. A
word is found only as a whole, so ``Eva`` is not found in ``evaluation``. A position is found
in any case, as a whole phrase only, never word by word, so ``Officer`` stays in ordinary
text when the position is ``Dam Safety Officer``. A position of fewer than four word characters
with no lower-case letter (IT, HR, C#) is found only as written, and one of a single character
(n, 5) is not searched for. Typos, diminutives and the forms that change a word's stem
(Kupka, Kupce) are not found. A name inside an e-mail address is found word by word, and a word
of fewer than five letters is found only with the capital it was stored with, so
``jana.novakova@example.com`` becomes ``jana.Expert 1@example.com``; the address is not masked
as a whole.

A name or a position that a block shows cut with dots is also found in that cut form, with and
without the dots, as a whole phrase. The words of a stranger's cut name that the cut left whole,
the ones before the last and the last when it has four letters or more, are also found one by
one, like a name. A roster registers at most 100 participants. Past that an expert is still
masked wherever a block shows the name in a row, but the name is not searched for anywhere else
in the text.
"""

import re
import threading
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from api.assistant.agent.prompt import clean_text

# The longest an expert's name and the longest position are in a data block, in characters.
# Fifty rows must stay small in a 16k-token window, so a position is cut as tight as a name.
EXPERT_LIMIT = 60
POSITION_LIMIT = 60
# A name or a position is matched whole, so it is cleaned but never cut for matching.
_MATCH_LIMIT = 10_000

# The two pieces of an opinion row that stand around the row's head, written once so that
# the renderer and the roster find the same rows.
ROW_MARK = "- "
ROW_HEAD_END = ": "
# What stands around the position in a row head, written once for the same reason.
POSITION_OPEN = " ("
POSITION_CLOSE = ")"


class Expert(Protocol):
    """What the roster reads of an opinion: the expert's name and position."""

    @property
    def expert_name(self) -> str:
        """The expert's name as the API gave it."""
        ...

    @property
    def position(self) -> str:
        """The expert's position as the API gave it."""
        ...


EXPERT_LABEL = re.compile(r"Expert \d+")


def expert_label(number: int) -> str:
    """Write the label of the number-th participant.

    :param number: The participant's number, from 1.
    :return: ``Expert <number>``.
    """
    return f"Expert {number}"


def opinion_head(opinion: Expert) -> str:
    """Write what stands between ``- `` and ``: `` in an opinion row.

    The renderer and the roster both call this, so the row a block holds and the row the
    roster looks for cannot drift apart.

    :param opinion: The opinion.
    :return: The expert's name and, in parentheses, the position when there is one; each
        cleaned and cut to its limit.
    """
    name = clean_text(opinion.expert_name, EXPERT_LIMIT)
    position = clean_text(opinion.position, POSITION_LIMIT)
    return f"{name}{POSITION_OPEN}{position}{POSITION_CLOSE}" if position else name


def _looks_cut(text: str, limit: int) -> bool:
    """Whether a name or position out of a block looks cut to the limit, with dots at its end."""
    return text.endswith("...") and len(text) > limit // 2


def split_head(head: str) -> tuple[str, str]:
    """Split a row head into the name and the position, as :func:`opinion_head` wrote them.

    The split is at the first opening bracket, because a name cannot hold one while a position
    can: ``Chairman (deputy)``. That relies on ``validate_name_format`` in ``api/schemas/auth.py``
    keeping brackets out of names (letters, spaces, hyphens and apostrophes only).

    :param head: What stands between ``- `` and ``: `` in an opinion row.
    :return: The name and the position; the position is empty when the head has none.
    """
    if head.endswith(POSITION_CLOSE):
        cut = head.find(POSITION_OPEN, 0, len(head) - len(POSITION_CLOSE))
        if cut > 0:
            return head[:cut], head[cut + len(POSITION_OPEN) : -len(POSITION_CLOSE)]
    return head, ""


# Letters that differ only by a diacritic count as one when a name is matched, so that a
# name typed without diacritics is still found.
_ACCENT_GROUPS = ("aá", "cč", "dď", "eéě", "ií", "nň", "oó", "rř", "sš", "tť", "uúů", "yý", "zž")
_GROUP_OF = {char: group for group in _ACCENT_GROUPS for char in group}

_VOWELS = frozenset("aeěiíouyýáéůúó")
# What a Czech word takes after its stem. One or two letters for the singular cases and longer
# ones for the plural, for the possessive forms of a surname built with -ov- and the -uv form
# (u with a ring), and for the adjective declensions: the hard one (-y, as in Novotny) and the
# soft one (-i with an acute accent, as in Krejci or Jiri). A feminine surname in -ova takes
# the plain cases. The words themselves are in the table of test_masking.py.
# fmt: off
_ENDINGS = frozenset([
    "a", "e", "ě", "i", "í", "o", "u", "y", "ý", "á", "é", "ou", "em", "ovi", "ům", "ách", "ech",
    "ích", "ami", "ové", "ových", "ovým", "ého", "ému", "ém", "ým", "ými", "ovou", "ová", "ího",
    "ímu", "ův", "ovo", "ovu", "ovy", "ovými", "ím", "ých", "ími",
])
# fmt: on
# A word that ends so loses the e before an ending: Marek takes Marka, Pavel takes Pavla.
_DROPS_E = frozenset(("ek", "ec", "el", "ěk"))
# Dropping a final vowel from a shorter word leaves too little to match on (Li, Xu).
_MIN_DECLINED = 3

_WORD_START = r"(?<!\w)"
# Whitespace, the hyphen and the other dashes that a double surname may join its parts with.
_NAME_SEPARATOR = re.compile(r"[\s\-\u2010-\u2015\u2212]+")
# A part of a name is searched for only with this many letters or digits, and a position of
# four or more word characters only if one of its words has this many. A shorter part is a
# symbol or an escape such as the backslash and n of a line break, and replacing it would tear
# a text apart.
_MIN_NAME_PART = 2
# The last word of a cut name is searched for alone only with this many letters: a word cut
# mid-word to fewer (The, of Theodorakis) would hit ordinary words.
_MIN_CUT_WORD = 4
# A word of a name this long is found in any case of its first letter. A shorter one, which
# may be an ordinary word (Will, Eva), keeps the case it was written in.
_MIN_LOOSE_CASE = 5
# An acronym is a position with fewer word characters than this and no lower-case letter (IT,
# HR, CTO, C#). It is matched only as written, with no ending: in any case it would rewrite the
# words it, hra and pro. A short position with lower-case letters (Sef, Boss) is a word, and
# is matched in any case with endings. A position of fewer than _MIN_POSITION characters
# (n, 5) is not searched for, as it would tear escapes and numbers out of a text.
_MIN_LOOSE_POSITION = 4
_MIN_POSITION = 2
# The most participants a roster registers, whether fetched or met as an unknown row. The
# pattern grows with them: 100 experts take about half a second to build, 300 take 14 seconds.
_MAX_REGISTERED = 100
# A label or a position placeholder already in a text. It is passed over, so that a participant
# named Expert, or Position, cannot rewrite the labels an earlier step put there.
_PLACEHOLDER = r"(?<!\w)Expert \d+(?!\w)|\[position(?: of Expert \d+)?\]"


# Characters that print nothing and that copy-pasting from a document leaves inside names, and
# the curly apostrophes (U+2019, U+02BC) that stand for the plain one.
_FOLDED: dict[int, str | None] = {
    **dict.fromkeys(map(ord, "\u00ad\u200b\u200c\u200d\u2060\ufeff")),
    **dict.fromkeys(map(ord, "\u2019\u02bc"), "'"),
}


def _comparable(text: str) -> str:
    """Write a text in the form names are compared in.

    Composed and combining accents become one character (``á``), full-width and other
    compatibility forms become plain letters, invisible characters are dropped and typographic
    apostrophes become the plain one, so a name matches however it was typed or pasted.
    """
    if text.isascii():
        return text
    return unicodedata.normalize("NFKC", text).translate(_FOLDED)


def _is_word_char(char: str) -> bool:
    """Whether the character is one that ``\\w`` matches."""
    return char.isalnum() or char == "_"


def _split_edges(word: str) -> tuple[str, str, str]:
    """Split a word into its leading non-word characters, its core and its trailing ones."""
    start = 0
    while start < len(word) and not _is_word_char(word[start]):
        start += 1
    end = len(word)
    while end > start and not _is_word_char(word[end - 1]):
        end -= 1
    return word[:start], word[start:end], word[end:]


def _bounded(char: str) -> bool:
    """Whether a name that starts or ends with this character must stand as a whole word.

    A letter with a case, or a digit, is part of a word. A character of a script that does
    not separate words, or a symbol, is not, so a name written in one is found inside a run
    of text.
    """
    return char.isdigit() or char.lower() != char.upper()


def _letter(char: str, *, exact_case: bool) -> str:
    """Write a pattern for one character, with its diacritic variants.

    :param char: The character.
    :param exact_case: Whether the pattern keeps the character's case; otherwise it is
        lower case, for a part of the pattern that is matched ignoring case.
    :return: A character class, or the escaped character when it has no variants.
    """
    group = _GROUP_OF.get(char.lower())
    if group is None:
        return re.escape(char)
    return f"[{group.upper() if exact_case and char.isupper() else group}]"


def _letters(text: str) -> str:
    """Write a pattern for a run of characters, ignoring case and diacritics."""
    return "".join(_letter(char, exact_case=False) for char in text)


def _trie(endings: Iterable[str]) -> str:
    """Write one pattern for a set of endings, sharing the letters they begin with.

    A pattern per ending, repeated for every word of every participant, is what makes the
    whole pattern slow to build and to run.

    :param endings: The endings; an empty one means the others are optional.
    :return: The pattern, or an empty string when there is no ending but the empty one.
    """
    branches: dict[str, set[str]] = {}
    for ending in endings:
        if ending:
            branches.setdefault(_letter(ending[0], exact_case=False), set()).add(ending[1:])
    if not branches:
        return ""
    body = "|".join(head + _trie(rest) for head, rest in sorted(branches.items()))
    return f"(?:{body})" + ("?" if "" in set(endings) else "")


_ENDING_PATTERN = _trie(_ENDINGS)


def _declined(stem: str, *, head_exact: bool, bare: bool) -> str:
    """Write a pattern for a stem followed by an ending.

    :param stem: The stem; its first letter is matched as the caller says, the rest
        ignoring case and diacritics.
    :param head_exact: Whether the first letter keeps its case.
    :param bare: Whether the stem may also stand without an ending.
    :return: The pattern.
    """
    ending = _ENDING_PATTERN + ("?" if bare else "")
    if head_exact:
        return _letter(stem[0], exact_case=True) + f"(?i:{_letters(stem[1:])}{ending})"
    return f"(?i:{_letters(stem)}{ending})"


def _inflected(core: str, *, head_exact: bool) -> str:
    """Write a pattern for a word in every case it takes, as far as the rules reach.

    :param core: The word, without punctuation at either end.
    :param head_exact: Whether the first letter keeps its case.
    :return: The pattern.
    """
    if len(core) == 1:
        return _letter(core, exact_case=True) if head_exact else f"(?i:{_letters(core)})"
    if core[-1].lower() in _VOWELS and len(core) >= _MIN_DECLINED:
        variants = [_declined(core[:-1], head_exact=head_exact, bare=False)]
    else:
        variants = [_declined(core, head_exact=head_exact, bare=True)]
    if core[-2:].lower() in _DROPS_E:
        variants.append(_declined(core[:-2] + core[-1], head_exact=head_exact, bare=False))
    return "(?:" + "|".join(variants) + ")"


def _word(word: str, *, exact_first: bool) -> str:
    """Write a pattern for one word, punctuation at its ends kept as it is.

    :param word: The word.
    :param exact_first: Whether a capital first letter of a short word must be found as a
        capital (see :data:`_MIN_LOOSE_CASE`). A word written in lower case, and a long word,
        is always matched ignoring the case of its first letter.
    :return: The pattern.
    """
    lead, core, tail = _split_edges(word)
    exact = exact_first and core[:1].isupper() and len(core) < _MIN_LOOSE_CASE
    body = _inflected(core, head_exact=exact) if core else ""
    return re.escape(lead) + body + re.escape(tail)


def _phrase(words: Sequence[str], separator: str, *, exact_first: bool) -> str:
    """Write a pattern for words that follow one another, found only as whole words.

    :param words: The words, none empty.
    :param separator: The pattern that stands between two words.
    :param exact_first: Whether a capital first letter of a short word must be found as a
        capital; otherwise the whole phrase is matched ignoring case.
    :return: The pattern.
    """
    body = separator.join(_word(word, exact_first=exact_first) for word in words)
    start = _WORD_START if _bounded(words[0][0]) else ""
    end = r"(?!\w)" if _bounded(words[-1][-1]) else ""
    return start + body + end


def _is_acronym(position: str) -> bool:
    """Whether a position is short and has no lower-case letter, so it is matched as written."""
    short = len(re.findall(r"\w", position)) < _MIN_LOOSE_POSITION
    return short and not any(char.islower() for char in position)


def _edge(char: str, bound: str) -> str:
    """Write the bound at one end of a pattern: none after a letter of a script without word
    spaces (a Chinese position is found inside a sentence), the given one otherwise.
    """
    return "" if char.isalpha() and not _bounded(char) else bound


def _as_written(words: Sequence[str]) -> str:
    """Write a pattern for words found exactly as written, case and ending included.

    A word character may touch neither end, unless the end is a letter of a script without
    word spaces, so ``C#`` is not found in ``C#10`` and ``.NET`` is not found in ``ASP.NET``.
    """
    start, end = _edge(words[0][0], _WORD_START), _edge(words[-1][-1], r"(?!\w)")
    return start + r"\s+".join(map(re.escape, words)) + end


def _position_regex(position: str) -> str | None:
    """Write the pattern that finds a position, or None when it is not searched for.

    An acronym is found as written. A word, or a phrase with a word of two characters or
    more, is found in any case with Czech endings. A short one with lower-case letters and a
    symbol (c#, c++) is found as written, unless it holds a backslash, so ``\\n`` cannot tear
    an escape.
    """
    words = position.split()
    has_word_char = re.search(r"\w", position) is not None
    if _is_acronym(position):
        return _as_written(words) if has_word_char else None
    if any(_letters_and_digits(word) >= _MIN_NAME_PART for word in words):
        return _phrase(words, r"\s+", exact_first=False)
    return _as_written(words) if has_word_char and "\\" not in position else None


def _letters_and_digits(word: str) -> int:
    """Count the characters of a word that are not punctuation at its ends."""
    return len(_split_edges(word)[1])


def _row_head(head: str) -> str:
    """Write a pattern for an opinion row's head, found only where a row has it."""
    return f"(?<={re.escape(ROW_MARK)}){re.escape(head)}(?={re.escape(ROW_HEAD_END)})"


@dataclass(frozen=True)
class _Alt:
    """What one alternative of the pattern puts in place of what it finds.

    :ivar length: Of what it looks for; the longest alternative goes first.
    :ivar replacement: The label or placeholder.
    :ivar exact: Whether it is an acronym; of two of one length, it goes first.
    """

    length: int
    replacement: str
    exact: bool = False


@dataclass(frozen=True)
class _Matcher:
    """The patterns that find what a roster hides, and what to put in its place.

    :ivar pattern: One group per alternative, in the order of ``replacements``.
    :ivar replacements: The text that replaces what each alternative found; None keeps it.
    """

    pattern: re.Pattern[str]
    replacements: tuple[str | None, ...]


@dataclass
class _Participant:
    """One expert of the turn.

    :ivar number: The label's number.
    :ivar names: The expert's name, cleaned and as written, whole; each is searched for whole
        and word by word. For a stranger met only as a cut row it holds the words before the
        cut, and the last word when it has at least four letters, in place of the whole name.
    :ivar cuts: The name as a block shows it cut with dots, and without the dots, when it was
        cut; each is searched for as a whole phrase only, so a word cut off at the end of a
        long name (``The``) is not searched for alone.
    :ivar heads: Every row head an opinion of this expert has been rendered with.
    """

    number: int
    names: set[str] = field(default_factory=set)
    cuts: set[str] = field(default_factory=set)
    heads: set[str] = field(default_factory=set)


class TurnRoster:
    """The experts a turn has met, filled as opinions are fetched.

    A turn fetches opinions in a few places (ahead of the model, in a tool, for the roster
    alone), on the event loop and on executor threads, so every method takes the lock.
    The same name keeps its label whichever list it turns up in.

    :ivar incomplete: True while the turn is about a project whose opinions have not been read
        into the roster, so a name may be missing from it.
    """

    def __init__(self) -> None:
        """Start with no participants."""
        self._lock = threading.Lock()
        self._by_name: dict[str, _Participant] = {}
        self._count = 0
        # True until the opinions of the project the turn is about are read into the roster.
        self.incomplete = False
        # A position to the position as written and the participants holding it. An acronym is
        # keyed by its exact spelling, any other position case folded.
        self._positions: dict[str, tuple[str, set[int]]] = {}
        self._matcher: _Matcher | None = None

    def add(self, opinions: Sequence[Expert]) -> None:
        """Register the experts of a list of opinions.

        Names and positions are kept whole and in composed Unicode form, both as a block
        shows them (cleaned) and as they were written, so a text that differs in either
        still matches.

        :param opinions: Opinions as fetched; an expert already registered keeps the label.
        """
        with self._lock:
            for opinion in opinions:
                participant = self._participant_of(opinion)
                if participant is not None:
                    self._remember(participant, opinion)
            self._matcher = None

    def _participant_of(self, opinion: Expert) -> _Participant | None:
        """Find or register the opinion's expert, or None; the caller holds the lock."""
        name = _comparable(clean_text(opinion.expert_name, _MATCH_LIMIT))
        if not name:
            return None
        cut = _comparable(clean_text(opinion.expert_name, EXPERT_LIMIT))
        # An expert first met as a stranger's row is keyed by the cut name, so look for that too.
        # Only the key: another fetched expert's cut is no proof of the same person.
        participant = self._by_name.get(name) or (self._by_name.get(cut) if cut != name else None)
        if participant is None:
            if len(self._by_name) >= _MAX_REGISTERED:
                return None
            self._count += 1
            participant = self._by_name[name] = _Participant(self._count)
        participant.names.update((name, _comparable(" ".join(opinion.expert_name.split()))))
        if cut != name:  # a block shows a long name cut with dots; a model may quote it so
            participant.cuts.update((cut, cut.removesuffix("...")))
        return participant

    def _find(self, name: str) -> _Participant | None:
        """Find a participant by a name, whole or cut; the caller holds the lock."""
        found = self._by_name.get(name)
        if found is None:
            found = next((p for p in self._by_name.values() if name in p.cuts), None)
        return found

    def _remember(self, participant: _Participant, opinion: Expert) -> None:
        """Record the opinion's row head and position for its expert; the caller holds the lock."""
        participant.heads.add(_comparable(opinion_head(opinion)))
        full = clean_text(opinion.position, _MATCH_LIMIT)
        cut = clean_text(opinion.position, POSITION_LIMIT)  # as a block shows a long one
        forms = [full, " ".join(opinion.position.split())]
        if cut != full:
            forms += [cut, cut.removesuffix("...")]
        for position in forms:
            self._note_position(participant, position)

    def _note_position(self, participant: _Participant, position: str) -> None:
        """Record that a participant holds a position; the caller holds the lock."""
        position = _comparable(position)
        if len(position) >= _MIN_POSITION:
            key = position if _is_acronym(position) else position.casefold()
            _, holders = self._positions.setdefault(key, (position, set()))
            holders.add(participant.number)

    def label_for(self, head: str) -> str:
        """Give the label of a row head, registering it as a new participant if it is unknown.

        The shape mask meets rows of experts the roster never fetched. Numbering them from 1
        would reuse the labels of the experts it did, so they get the next free ones. The head
        is split into a name and a position (see :func:`split_head`), and each is searched for
        in the rest of the trace under that label. A name the roster knows keeps its label,
        whatever position the row gives it.

        :param head: What stands between ``- `` and ``: `` in an opinion row.
        :return: The label.
        """
        text = _comparable(head)
        with self._lock:
            for participant in self._by_name.values():
                if text in participant.heads or text in participant.names:
                    return expert_label(participant.number)
            name, position = split_head(text)
            owner = self._find(name)
            if owner is None:
                self._count += 1
                if not name or len(self._by_name) >= _MAX_REGISTERED:
                    return expert_label(self._count)
                owner = self._by_name[name] = _Participant(self._count)
                if _looks_cut(name, EXPERT_LIMIT):
                    dotless = name.removesuffix("...")
                    owner.cuts.update((name, dotless))
                    # Only the last word can be cut mid-word, so the words before it are whole,
                    # and the last one, whole when the cut fell between words, is searched for
                    # alone when it is long enough not to hit ordinary words.
                    breaks = list(_NAME_SEPARATOR.finditer(dotless))
                    if breaks:
                        owner.names.add(dotless[: breaks[-1].start()])
                        last = dotless[breaks[-1].end() :]
                        if _letters_and_digits(last) >= _MIN_CUT_WORD:
                            owner.names.add(last)
                else:
                    owner.names.add(name)
            owner.heads.add(text)
            self._note_position(owner, position)
            if _looks_cut(position, POSITION_LIMIT):
                self._note_position(owner, position.removesuffix("..."))
            self._matcher = None
            return expert_label(owner.number)

    def drop_matcher(self) -> None:
        """Forget the built pattern, which is large; the next use of the roster builds it again."""
        with self._lock:
            self._matcher = None

    def matcher(self) -> "_Matcher | None":
        """Return the pattern for the participants registered so far.

        :return: The pattern, or None while nobody is registered.
        """
        with self._lock:
            if self._matcher is None and self._by_name:
                self._matcher = self._build()
            return self._matcher

    def _build(self) -> _Matcher:
        """Build the pattern; the caller holds the lock."""
        heads: dict[str, _Alt] = {}
        alts: dict[str, _Alt] = {}
        for participant in self._by_name.values():
            label = expert_label(participant.number)
            for head in participant.heads:
                heads.setdefault(_row_head(head), _Alt(len(head), label))
            for regex, alt in _name_alts(participant).items():
                alts.setdefault(regex, alt)
        for regex, alt in self._position_alts().items():
            alts.setdefault(regex, alt)
        return _assemble(heads, alts)

    def _position_alts(self) -> dict[str, _Alt]:
        """Write the alternatives for the positions; the caller holds the lock."""
        found: dict[str, _Alt] = {}
        for position, numbers in self._positions.values():
            regex = _position_regex(position)
            if regex is None:
                continue
            only = next(iter(numbers)) if len(numbers) == 1 else None
            replacement = "[position]" if only is None else f"[position of {expert_label(only)}]"
            found.setdefault(regex, _Alt(len(position), replacement, _is_acronym(position)))
        return found


def _name_alts(participant: _Participant) -> dict[str, _Alt]:
    """Write the alternatives that find a participant's name: the whole and each part."""
    label = expert_label(participant.number)
    found: dict[str, _Alt] = {}
    for name in participant.names:
        parts = [p for p in _NAME_SEPARATOR.split(name) if p]
        # The whole name is searched for even when its parts are too short to be searched for
        # alone (J K), so such a name is not left as it is.
        if len(parts) > 1 and sum(map(_letters_and_digits, parts)) >= _MIN_NAME_PART:
            phrase = _phrase(parts, _NAME_SEPARATOR.pattern, exact_first=False)
            found.setdefault(phrase, _Alt(len(name), label))
        for part in parts:
            if _letters_and_digits(part) >= _MIN_NAME_PART:
                found.setdefault(_phrase([part], "", exact_first=True), _Alt(len(part), label))
    for cut in participant.cuts:
        parts = [p for p in _NAME_SEPARATOR.split(cut) if p]
        if sum(map(_letters_and_digits, parts)) >= _MIN_NAME_PART:
            phrase = _phrase(parts, _NAME_SEPARATOR.pattern, exact_first=False)
            found.setdefault(phrase, _Alt(len(cut), label))
    return found


def _assemble(heads: dict[str, _Alt], alts: dict[str, _Alt]) -> _Matcher:
    """Join the row heads, then the names and positions, into one pattern, longest first.

    An acronym goes first of two of one length, so a tie does not depend on who was met first.
    """
    row_heads = sorted(heads.items(), key=lambda item: -item[1].length)
    ordered = sorted(alts.items(), key=lambda item: (-item[1].length, not item[1].exact))
    # Nearly every alternative begins by checking for the start of a word. Checked once for
    # all of them, the engine skips the middle of a word without trying each.
    at_word_start = [
        (r.removeprefix(_WORD_START), a) for r, a in ordered if r.startswith(_WORD_START)
    ]
    elsewhere = [(r, a) for r, a in ordered if not r.startswith(_WORD_START)]
    # The row heads stay in the pattern for a row outside a block, which the shape mask does
    # not read.
    pieces = [f"({_PLACEHOLDER})", *(f"({regex})" for regex, _ in row_heads)]
    if at_word_start:
        pieces.append(_WORD_START + "(?:" + "|".join(f"({r})" for r, _ in at_word_start) + ")")
    pieces.extend(f"({regex})" for regex, _ in elsewhere)
    replacements = (None, *(a.replacement for _, a in [*row_heads, *at_word_start, *elsewhere]))
    return _Matcher(re.compile("|".join(pieces)), replacements)


def mask_participants(text: str, roster: TurnRoster) -> str:
    """Replace the participants' names and positions in a text with their labels.

    The text is read once and what is put in is never read again, and a label or a position
    placeholder that is already in the text is passed over, so a label cannot be mistaken for
    a name. An opinion row whose head the roster knows becomes ``- Expert N: <values>``.

    :param text: Any text. It is read in the form names are compared in (see
        :func:`_comparable`), so a name typed with a combining accent, in full-width letters
        or with an invisible character in it is found, and the text comes back in that form.
    :param roster: The turn's participants.
    :return: The text with every name replaced by ``Expert N`` and every position by
        ``[position of Expert N]``, or by ``[position]`` when several hold it.
    """
    matcher = roster.matcher()
    if matcher is None or not text:
        return text
    text = _comparable(text)
    replacements = matcher.replacements

    def replace(match: re.Match[str]) -> str:
        replacement = replacements[(match.lastindex or 1) - 1]
        return match.group(0) if replacement is None else replacement

    return matcher.pattern.sub(replace, text)
