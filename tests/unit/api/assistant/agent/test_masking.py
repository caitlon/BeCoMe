"""Tests for the turn's roster and the mask that hides its participants in a trace."""

import re
from typing import Any
from unittest.mock import patch

import pytest

from api.assistant.agent import masking
from api.assistant.agent.masking import TurnRoster, mask_participants
from api.assistant.agent.tools import mask_opinion_names, mask_opinion_rows, render_opinions
from api.assistant.views import OpinionView


def _opinion(name: str, position: str = "Hydrologist") -> OpinionView:
    return OpinionView(
        expert_name=name,
        position=position,
        lower_bound=37.0,
        peak=42.0,
        upper_bound=47.0,
        centroid=42.0,
    )


def _roster(*specs: OpinionView | str | tuple[str, str]) -> TurnRoster:
    """Build a roster from opinions, names, or (name, position) pairs."""
    roster = TurnRoster()
    roster.add(
        [
            spec
            if isinstance(spec, OpinionView)
            else _opinion(spec)
            if isinstance(spec, str)
            else _opinion(*spec)
            for spec in specs
        ]
    )
    return roster


def _hide(text: str, roster: TurnRoster) -> str:
    """Mask a text the way a trace does: the rows of opinions blocks, then names."""
    return mask_participants(mask_opinion_rows(text, roster), roster)


def _forms(
    names: tuple[object, ...], template: str, forms: list[str], expected: str = "{}"
) -> list[Any]:
    """One case per way of writing a name: ``{}`` in the template and the result is the form."""
    return [
        pytest.param(names, template.replace("{}", form), expected.replace("{}", form), id=form)
        for form in forms
    ]


_CURLY = chr(0x2019)  # right single quotation mark
_MODIFIER = chr(0x02BC)  # modifier letter apostrophe
_EN_DASH = chr(0x2013)
_ZWSP = chr(0x200B)  # zero-width space
_SHY = chr(0x00AD)  # soft hyphen
_ACUTE = chr(0x0301)  # combining acute accent
_FULLWIDTH = (
    chr(0xFF2E) + chr(0xFF4F) + chr(0xFF56) + "á" + chr(0xFF4B)
)  # the name Novak in full-width letters
_NOVAK = ("Jan Novák",)
_NOVAK_FORMS = (  # noqa: SIM905
    "Novák Nováka Novákovi Novákem Novákovým Novákové Novákův Novákovo Novákovu Novákovy "
    "Novákovými Novak Novakovi NOVÁK"
).split()
_ROWS = [
    # Czech cases of a masculine surname, with the possessives, and without diacritics
    *_forms(
        _NOVAK,
        "Co říká {}?",
        _NOVAK_FORMS,
        "Co říká Expert 1?",
    ),
    *_forms(
        ("Jana Nováková",),
        "S {} jsem mluvil",
        ["Nováková", "Novákové", "Novákovou", "Novákovu", "Novakova"],
        "S Expert 1 jsem mluvil",
    ),
    *_forms(
        ("Eva Svobodová",),
        "Dej to {}",
        ["Eva", "Evy", "Evě", "Evou", "Evu", "Eve"],
        "Dej to Expert 1",
    ),
    # the adjective declensions: soft (Krejci, Jiri) and hard (Novotny)
    *_forms(("Jiří Svoboda",), "S {}", ["Jiří", "Jiřího", "Jiřímu", "Jiřím"], "S Expert 1"),
    *_forms(
        ("Petr Krejčí",),
        "S {}",
        ["Krejčí", "Krejčího", "Krejčímu", "Krejčím", "Krejčích", "Krejčími"],
        "S Expert 1",
    ),
    *_forms(
        ("Novotný",),
        "S {}",
        ["Novotný", "Novotného", "Novotnému", "Novotným", "Novotní", "Novotných", "Novotnými"],
        "S Expert 1",
    ),
    # a name that loses its e before an ending
    *_forms(("Marek",), "S {}", ["Marka", "Markovi", "Markem", "Marek"], "S Expert 1"),
    *_forms(("Pavel",), "S {}", ["Pavla", "Pavlovi"], "S Expert 1"),
    *_forms(("Němec",), "S {}", ["Němce", "Němcem"], "S Expert 1"),
    # a roster nobody joined changes nothing
    ((), "Novák said hello", "Novák said hello"),
    # the whole name, its parts, another order, other dashes
    (("Eva Svobodová",), "Řekni to Evě Svobodové.", "Řekni to Expert 1."),
    (
        ("Jana Nováková-Svobodová",),
        "Jana Nováková-Svobodová a paní Svobodová",
        "Expert 1 a paní Expert 1",
    ),
    (("Jana Nováková-Svobodová",), f"Jana Nováková{_EN_DASH}Svobodová", "Expert 1"),
    (_NOVAK, "Ask Jan Novák now", "Ask Expert 1 now"),
    (_NOVAK, "Ask Novák Jan now", "Ask Expert 1 Expert 1 now"),
    *_forms(_NOVAK, "Ask {} now", ["Jan", "Novák"], "Ask Expert 1 now"),
    # case: the whole name and long words in any case, short words keep the case they have
    (_NOVAK, "co řekl jan novák", "co řekl Expert 1"),
    (_NOVAK, "komu novákovi", "komu Expert 1"),
    (("jan novák",), "Jan Novák", "Expert 1"),
    (("Will Young",), "Will said he will go", "Expert 1 said he will go"),
    (("Eva Svobodová",), "eva and evaluation", "eva and evaluation"),
    *_forms(
        ("Eva Svobodová",),
        "The {} is done",
        ["evaluation", "Evropa", "Europe", "Event", "KEva", "Evidence"],
        "The {} is done",
    ),
    # how the same letters were composed, cleaned or pasted
    (_NOVAK, f"Co říká Nova{_ACUTE}k?", "Co říká Expert 1?"),
    (
        ((f"Jan Nova{_ACUTE}k", f"Vedouci{_ACUTE} odboru"),),
        "Novák je Vedoucí odboru",
        "Expert 1 je [position of Expert 1]",
    ),
    (("Novák",), f"Ask {_FULLWIDTH}.", "Ask Expert 1."),
    (("Novák",), f"Ask Nov{_ZWSP}ák.", "Ask Expert 1."),
    (("Novák",), f"Ask Nov{_SHY}ák.", "Ask Expert 1."),
    ((f"Nov{_SHY}ák",), "Novák", "Expert 1"),
    *_forms(
        ("O'Brien",),
        "Ask {}.",
        ["O'Brien", f"O{_CURLY}Brien", f"O{_MODIFIER}Brien"],
        "Ask Expert 1.",
    ),
    ((f"O{_CURLY}Brien",), "Ask O'Brien.", "Ask Expert 1."),
    (("Jan   <Novák>",), "Jan   <Novák> spoke", "Expert 1 spoke"),
    (
        ("Bartholomew Alexander Montgomery Featherstonehaugh-Smythe Svobodová",),
        "Ask Svobodové and Bartholomew",
        "Ask Expert 1 and Expert 1",
    ),
    (("王伟",), "请问王伟说", "请问Expert 1说"),
    # names and positions made of symbols or of short parts
    (
        (("A.* (B)+ [x]", "R&D (head)+ ^$"),),
        "A.* (B)+ [x] and R&D (head)+ ^$",
        "Expert 1 and [position of Expert 1]",
    ),
    ((("A.* (B)+ [x]", "R&D (head)+ ^$"),), "Axyz BB x", "Axyz BB x"),
    (("J K", "J Novák"), "J K and J Novák and J", "Expert 1 and Expert 2 and J"),
    (("Zed \\n Smith",), "one\\ntwo", "one\\ntwo"),
    ((("Alice Moore", "-"), ("Bob Green", "()")), "a - b (c)", "a - b (c)"),
    (("Alice Moore", "Expert Kowalski"), "Expert 1 and Expert Kowalski", "Expert 1 and Expert 2"),
    # a name that loses its e and softens a consonant (Zbynek -> Zbynka), and a very short one
    *_forms(("Zbyněk",), "Ptal se {}.", ["Zbyněk", "Zbyňka", "Zbyňkovi"], "Ptal se Expert 1."),
    (("Xu Ming",), "Xa, Xu, Xuan", "Xa, Expert 1, Xuan"),
    # two participants who share a surname: the surname alone is the first one's
    (
        ("Jan Novák", "Petr Novák"),
        "Novák; Jan Novák; Petr Novák; Petr",
        "Expert 1; Expert 1; Expert 2; Expert 2",
    ),
    # acronyms only as written, edges included; words and long positions in any case
    (
        (("Alice Moore", "IT"), ("Bob Green", "HR"), ("Carol White", "PR")),
        "IT, HR and PR, but it, hra, pro, PRO and ITs",
        "[position of Expert 1], [position of Expert 2] and [position of Expert 3], "
        "but it, hra, pro, PRO and ITs",
    ),
    (
        (("Alice Moore", "C#"), ("Bob Green", ".NET")),
        "C#, (C#), C#istka, C#10, ASP.NET, .NET",
        "[position of Expert 1], ([position of Expert 1]), C#istka, C#10, ASP.NET, "
        "[position of Expert 2]",
    ),
    (
        (("Alice Moore", "IT"), ("Bob Green", "it")),
        "A is IT, B is it",
        "A is [position of Expert 1], B is [position of Expert 2]",
    ),
    (
        (("Alice Moore", "LEAD"), ("Bob Green", "CTO")),
        "the lead said, CTO and cto",
        "the [position of Expert 1] said, [position of Expert 2] and cto",
    ),
    (
        (("Alice Moore", "Šéf"),),
        "Ptal se šéfa a šéfem",
        "Ptal se [position of Expert 1] a [position of Expert 1]",
    ),
    ((("Alice Moore", "n"), ("Bob Green", "5")), "line\\n- x, 5 experts", "line\\n- x, 5 experts"),
    # a Chinese position inside a sentence; lower-case symbol positions; a backslash one is left
    ((("Alice Moore", "社長"),), "彼は社長です", "彼は[position of Expert 1]です"),
    (
        (("Alice Moore", "c#"), ("Bob Green", "c++"), ("Carol White", "f#")),
        "c#, c++ and f#, but C# and c#x",
        "[position of Expert 1], [position of Expert 2] and [position of Expert 3], but C# and c#x",
    ),
    ((("Alice Moore", "\\n"),), "line\\n- x and \\n", "line\\n- x and \\n"),
    # of two spellings that tie, the acronym wins whichever expert was met first
    (
        (("Bob Green", "it"), ("Alice Moore", "IT")),
        "IT and it",
        "[position of Expert 2] and [position of Expert 1]",
    ),
    # a known gap: an address keeps the part of the name that is too short to be searched for
    (("Jana Nováková",), "jana.novakova@example.com", "jana.Expert 1@example.com"),
    *_forms(
        (("Alice Moore", "ředitel odboru"),),
        "Ptal se {}.",
        ["ředitel odboru", "ředitele odboru", "ředitelem odboru"],
        "Ptal se [position of Expert 1].",
    ),
    ((("Alice Moore", ""),), "Alice Moore said so", "Expert 1 said so"),
    (
        (("Alice Moore", "Hydrologist"), ("Alice Moore", "Dam Safety Officer")),
        "Hydrologist and dam safety officer",
        "[position of Expert 1] and [position of Expert 1]",
    ),
    # positions: any case, whole phrase only, a shared one is not attributed
    (
        (("Alice Moore", "Dam Safety Officer at Lipno"),),
        "She is a dam safety officer at Lipno.",
        "She is a [position of Expert 1].",
    ),
    (
        (("Alice Moore", "Dam Safety Officer at Lipno"),),
        "The officer checked safety at the dam.",
        "The officer checked safety at the dam.",
    ),
    ((("Alice Moore", "Hydrologist"),), "the hydrologist said", "the [position of Expert 1] said"),
    (("Alice Moore", "Bob Green"), "A Hydrologist spoke.", "A [position] spoke."),
    (
        (("Alice Moore", "Vedoucí odboru"),),
        "Rozhodl vedoucí odboru.",
        "Rozhodl [position of Expert 1].",
    ),
    (
        (("Alice Moore", "Assistant to Bob"), "Bob Green"),
        "Alice is Assistant to Bob",
        "Expert 1 is [position of Expert 1]",
    ),
]


@pytest.mark.parametrize(("names", "text", "expected"), _ROWS)
def test_a_participant_is_found_however_it_is_written(names, text, expected):
    """
    GIVEN a roster of participants, each a name or a (name, position) pair
    WHEN a text writes a name or a position in some form
    THEN each form that names a participant becomes its label or placeholder, and an ordinary
        word, a lone initial or a symbol that merely looks like one stays as it is
    """
    assert mask_participants(text, _roster(*names)) == expected


def test_the_same_name_keeps_its_label_and_a_new_one_gets_the_next():
    """
    GIVEN a roster that met Alice, then Bob, then Alice again in a later list with Carol
    WHEN a text names the three
    THEN Alice is Expert 1, Bob Expert 2 and Carol Expert 3
    """
    roster = _roster("Alice", "Bob")
    roster.add([_opinion("Alice"), _opinion("Carol")])

    assert mask_participants("Alice Bob Carol", roster) == "Expert 1 Expert 2 Expert 3"


def test_an_expert_added_after_the_pattern_was_built_is_masked():
    """
    GIVEN a roster whose pattern was built for one expert
    WHEN a second expert is added
    THEN the second name is masked too
    """
    roster = _roster("Alice Moore")
    assert mask_participants("Bob Green", roster) == "Bob Green"

    roster.add([_opinion("Bob Green")])

    assert mask_participants("Bob Green", roster) == "Expert 2"


def test_a_pattern_that_cannot_be_built_raises_instead_of_returning_the_text():
    """
    GIVEN a roster whose pattern fails to build
    WHEN a text is masked
    THEN the failure reaches the caller, and the text does not come back as it was
    """
    roster = _roster("Alice Moore")

    with (
        patch.object(TurnRoster, "_build", side_effect=re.error("too big")),
        pytest.raises(re.error),
    ):
        mask_participants("Alice Moore", roster)


def test_a_roster_past_its_cap_still_masks_the_rows_but_not_the_name_elsewhere():
    """
    GIVEN a roster capped at two participants that is offered three experts, and a block of
        the three followed by the third one's name
    WHEN the text is masked
    THEN the third expert's row is masked under a label of its own, the name after the block
        is left, and the first two are masked everywhere
    """
    experts = [_opinion(name) for name in ("Alice Moore", "Bob Green", "Carol White")]
    with patch.object(masking, "_MAX_REGISTERED", 2):
        roster = _roster(*experts)
        masked = _hide(render_opinions(experts) + "\nAlice Bob Carol", roster)

    assert masked.count("lower=37.00") == 3
    assert "- Expert 3: lower=37.00" in masked
    assert "White" not in masked
    assert masked.endswith("\nExpert 1 Expert 2 Carol")


class TestBlockRows:
    """A row of an opinions block takes the label of the roster."""

    @pytest.mark.parametrize("layout_word", ["Number", "lower", "opinions", "centroid"])
    def test_a_name_that_is_a_word_of_the_block_layout_cannot_hide_other_rows(self, layout_word):
        """
        GIVEN a participant named after a word of the block layout, and a block that also
            holds an expert the roster never met
        WHEN the block is masked
        THEN the unknown expert's row loses its name all the same
        """
        block = render_opinions([_opinion(layout_word), _opinion("Stranger Unknown")])

        masked = _hide(block, _roster(layout_word))

        assert "Stranger" not in masked
        assert "Unknown" not in masked
        assert masked.count("37.00") == 2

    def test_a_known_row_is_labelled_from_the_roster(self):
        """
        GIVEN a block of two opinions, and a roster that met them in the other order
        WHEN the block is masked with the roster
        THEN each row carries its participant's label and the numbers stay
        """
        alice, bob = _opinion("Alice Moore"), _opinion("Bob Green")

        masked = mask_participants(render_opinions([alice, bob]), _roster(bob, alice))

        assert masked.index("- Expert 2: lower=37.00") < masked.index("- Expert 1: lower=37.00")
        assert "Alice" not in masked

    def test_an_unknown_row_never_takes_a_label_the_roster_gave_someone_else(self):
        """
        GIVEN a roster that met Bob and Alice, and a block of Alice and a stranger, where
            numbering the rows from 1 would call the stranger Expert 2, which is Alice
        WHEN the block is masked with the roster
        THEN Alice is Expert 2, the stranger is Expert 3, and the stranger's name is masked
            elsewhere in the text under that label
        """
        alice, stranger = _opinion("Alice Moore"), _opinion("Stranger Unknown")
        roster = _roster("Bob Green", alice)

        masked = _hide(render_opinions([alice, stranger]) + "\nStranger spoke", roster)

        assert "- Expert 2: lower=37.00" in masked
        assert "- Expert 3: lower=37.00" in masked
        assert masked.endswith("\nExpert 3 spoke")
        assert "Stranger" not in masked

    def test_a_name_longer_than_a_block_shows_has_one_label_in_the_row_and_elsewhere(self):
        """
        GIVEN an expert whose name is longer than the block shows, so the row holds a cut head
        WHEN a block and a later mention of the whole name are masked
        THEN the row and the mention carry the same label
        """
        long_name = "Bartholomew Alexander Montgomery Featherstonehaugh-Smythe Svobodová"
        expert = _opinion(long_name)
        assert len(long_name) > masking.EXPERT_LIMIT

        masked = _hide(render_opinions([expert]) + "\nAsk Svobodové", _roster(expert))

        assert "- Expert 1: lower=37.00" in masked
        assert masked.endswith("\nAsk Expert 1")
        assert "Svobodov" not in masked

    def test_the_shape_mask_leaves_a_labelled_row_as_it_is(self):
        """
        GIVEN a block whose rows already read Expert 2 and Expert 1, in that order
        WHEN the shape mask is applied
        THEN the labels are not renumbered
        """
        block = (
            "<project_data>\nNumber of opinions: 2\n"
            "- Expert 2: lower=1.00, peak=2.00, upper=3.00, centroid=2.00\n"
            "- Expert 1: lower=1.00, peak=2.00, upper=3.00, centroid=2.00\n"
            "</project_data>"
        )

        assert mask_opinion_names(block) == block

    def test_a_block_with_escaped_newlines_is_labelled_too(self):
        """
        GIVEN a block inside repr(exc), where each newline is a backslash and an n
        WHEN it is masked
        THEN the rows carry the roster's labels and no name is left
        """
        alice, bob = _opinion("Alice Moore"), _opinion("Bob Green")
        error = repr(ValueError(render_opinions([alice, bob])))

        masked = _hide(error, _roster(bob, alice))

        assert "Alice" not in masked
        assert "Bob" not in masked
        assert "\\n- Expert 2: lower=37.00" in masked
        assert "\\n- Expert 1: lower=37.00" in masked

    @pytest.mark.parametrize("known", [True, False], ids=["known", "unknown"])
    @pytest.mark.parametrize(
        "wrap", [str, lambda block: repr(ValueError(block))], ids=["text", "repr"]
    )
    def test_a_crafted_name_never_survives_a_row_whether_or_not_the_roster_knows_it(
        self, known, wrap
    ):
        """
        GIVEN a block with a row whose name holds the fixed tail of a row, parentheses and a
            name the roster does know, and a roster that has or has not met that row's expert
        WHEN the block is masked by the roster and then by shape
        THEN nothing of the crafted name or its position is left, in the text or in a repr
        """
        crafted = "Bob: lower=1.00, peak=2.00, upper=3.00, centroid=4.00 SECRETX (Chair)"
        other = _opinion("Bob")
        roster = _roster(other, *([_opinion(crafted, "Chair")] if known else []))
        block = render_opinions([other, _opinion(crafted, "Chair")])

        masked = _hide(wrap(block), roster)

        assert "SECRETX" not in masked
        assert "Chair" not in masked
        assert "Bob" not in masked
        assert masked.count("lower=37.00") == 2

    @pytest.mark.parametrize("known", [True, False], ids=["known", "unknown"])
    def test_a_crafted_position_never_survives_a_row_either(self, known):
        """
        GIVEN a block with a row whose position holds the fixed tail of a row and a closing
            parenthesis, and a roster that has or has not met that row's expert
        WHEN the block is masked by the roster and then by shape
        THEN nothing of the crafted position is left
        """
        position = "Chair): lower=1.00, peak=2.00, upper=3.00, centroid=4.00 SECRETY (x"
        crafted = _opinion("Carol", position)
        roster = _roster(*([crafted] if known else []))

        masked = _hide(render_opinions([crafted]), roster)

        assert "SECRETY" not in masked
        assert "Chair" not in masked
        assert "Carol" not in masked


@pytest.mark.parametrize(
    "word", ["", "a", "_a_", "(C#)", "...", "--x--", "a b", "\n.x\n", "社長!", "ř_"]
)
def test_the_edges_of_a_word_split_as_a_regular_expression_would_split_them(word):
    """
    GIVEN words with and without punctuation, underscores and non-ASCII letters at the ends
    WHEN they are split into leading symbols, core and trailing symbols
    THEN the parts are those of the regular expression the split replaced
    """
    expected = re.fullmatch(r"(\W*)(.*?)(\W*)", word, re.DOTALL)
    assert expected is not None
    assert masking._split_edges(word) == expected.groups()
