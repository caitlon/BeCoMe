"""Tests for the turn's roster and the mask that hides its participants in a trace."""

import re
from unittest.mock import patch

import pytest

from api.assistant.agent.masking import TurnRoster, label_known_rows, mask_participants
from api.assistant.agent.tools import mask_opinion_names, render_opinions
from api.assistant.views import OpinionView


class _Opinion(OpinionView):
    """An opinion that carries the position the roster reads."""

    position: str


def _opinion(name: str, position: str = "Hydrologist") -> _Opinion:
    return _Opinion(
        expert_name=name,
        position=position,
        lower_bound=37.0,
        peak=42.0,
        upper_bound=47.0,
        centroid=42.0,
    )


def _hide(text: str, roster: TurnRoster) -> str:
    """Mask a text the way a trace does: known rows, the rest of the rows by shape, then names."""
    return mask_participants(mask_opinion_names(label_known_rows(text, roster)), roster)


def _roster(*opinions: OpinionView) -> TurnRoster:
    roster = TurnRoster()
    roster.add(list(opinions))
    return roster


class TestNames:
    """A name is found as the whole name and as each word, in the cases a Czech word takes."""

    @pytest.mark.parametrize(
        "text",
        [
            "Novák",
            "Nováka",
            "Novákovi",
            "Novákem",
            "Novákovým",
            "Novákové",
            "Novak",
            "Novakovi",
            "NOVÁK",
        ],
    )
    def test_a_masculine_surname_is_found_in_its_cases(self, text):
        """
        GIVEN a participant named Jan Novák
        WHEN a text holds one of the forms of the surname
        THEN the form is replaced by the participant's label
        """
        roster = _roster(_opinion("Jan Novák"))

        assert mask_participants(f"Co říká {text}?", roster) == "Co říká Expert 1?"

    @pytest.mark.parametrize("text", ["Nováková", "Novákové", "Novákovou", "Novákovu", "Novakova"])
    def test_a_feminine_surname_is_found_in_its_cases(self, text):
        """
        GIVEN a participant named Jana Nováková
        WHEN a text holds one of the forms of the surname
        THEN the form is replaced by the participant's label
        """
        roster = _roster(_opinion("Jana Nováková"))

        assert mask_participants(f"S {text} jsem mluvil", roster) == "S Expert 1 jsem mluvil"

    @pytest.mark.parametrize("text", ["Eva", "Evy", "Evě", "Evou", "Evu", "Eve"])
    def test_a_first_name_ending_in_a_vowel_is_found_in_its_cases(self, text):
        """
        GIVEN a participant named Eva Svobodová
        WHEN a text holds a form of the first name
        THEN it is replaced by the label
        """
        roster = _roster(_opinion("Eva Svobodová"))

        assert mask_participants(f"Dej to {text}", roster) == "Dej to Expert 1"

    @pytest.mark.parametrize(
        ("name", "text"),
        [
            ("Marek", "Marka"),
            ("Marek", "Markovi"),
            ("Marek", "Markem"),
            ("Marek", "Marek"),
            ("Pavel", "Pavla"),
            ("Pavel", "Pavlovi"),
            ("Němec", "Němce"),
            ("Němec", "Němcem"),
        ],
    )
    def test_a_name_that_loses_its_e_is_found_with_and_without_it(self, name, text):
        """
        GIVEN a participant whose name ends in ek, el or ec
        WHEN a text holds a form with the e dropped, or the name itself
        THEN it is replaced by the label
        """
        roster = _roster(_opinion(name))

        assert mask_participants(f"Ptal se {text}.", roster) == "Ptal se Expert 1."

    def test_the_whole_name_becomes_one_label(self):
        """
        GIVEN a participant named Eva Svobodová
        WHEN a text holds the full name in the dative
        THEN it becomes one label, not one per word
        """
        roster = _roster(_opinion("Eva Svobodová"))

        assert mask_participants("Řekni to Evě Svobodové.", roster) == "Řekni to Expert 1."

    def test_a_hyphenated_name_is_found_whole_and_by_part(self):
        """
        GIVEN a participant with a double surname
        WHEN a text holds the whole of it and then one part
        THEN both are replaced
        """
        roster = _roster(_opinion("Jana Nováková-Svobodová"))

        text = "Jana Nováková-Svobodová a paní Svobodová"
        assert mask_participants(text, roster) == "Expert 1 a paní Expert 1"

    @pytest.mark.parametrize(
        "text",
        ["evaluation", "Evropa", "Europe", "Event", "KEva", "Evidence"],
    )
    def test_a_word_that_only_contains_a_name_is_left_alone(self, text):
        """
        GIVEN a participant named Eva
        WHEN a text holds ordinary words that begin or end like the name
        THEN they survive
        """
        roster = _roster(_opinion("Eva Svobodová"))

        assert mask_participants(f"The {text} is done", roster) == f"The {text} is done"

    def test_the_case_of_the_first_letter_is_kept(self):
        """
        GIVEN a participant named Will
        WHEN a text holds the name and the verb
        THEN only the name is replaced
        """
        roster = _roster(_opinion("Will Young"))

        assert mask_participants("Will said he will go", roster) == "Expert 1 said he will go"

    def test_the_same_name_keeps_its_label_and_a_new_one_gets_the_next(self):
        """
        GIVEN a roster that met Alice, then Bob, then Alice again in a later list
        WHEN a text names all three mentions
        THEN Alice is Expert 1 and Bob is Expert 2
        """
        roster = _roster(_opinion("Alice"), _opinion("Bob"))
        roster.add([_opinion("Alice"), _opinion("Carol")])

        assert mask_participants("Alice Bob Carol", roster) == "Expert 1 Expert 2 Expert 3"


class TestHowANameIsWritten:
    """A name is found however the same letters were composed, cleaned or cased."""

    def test_a_text_with_combining_accents_matches_a_name_with_composed_ones(self):
        """
        GIVEN a participant whose name has composed accents
        WHEN a text spells the same name with a letter and a combining accent
        THEN the name is replaced
        """
        roster = _roster(_opinion("Jan Nov\u00e1k"))

        assert mask_participants("Co \u0159\u00edk\u00e1 Nova\u0301k?", roster) == (
            "Co \u0159\u00edk\u00e1 Expert 1?"
        )

    def test_a_name_with_combining_accents_matches_a_composed_text(self):
        """
        GIVEN a participant whose name came with combining accents, and a position that did
        WHEN a text spells both with composed letters
        THEN both are replaced
        """
        roster = _roster(_opinion("Jan Nova\u0301k", "Vedouci\u0301 odboru"))

        text = "Nov\u00e1k je Vedouc\u00ed odboru"
        assert mask_participants(text, roster) == "Expert 1 je [position of Expert 1]"

    def test_the_whole_of_a_name_cut_in_a_block_is_still_found(self):
        """
        GIVEN a participant whose name is longer than a block shows
        WHEN a text holds the whole name
        THEN every word of it is replaced, including those the block cut off
        """
        name = "Bartholomew Alexander Montgomery Featherstonehaugh-Smythe Svobodov\u00e1"
        roster = _roster(_opinion(name))

        assert len(name) > 60
        assert mask_participants("Ask Svobodov\u00e9 and Bartholomew", roster) == (
            "Ask Expert 1 and Expert 1"
        )

    def test_a_name_is_found_as_it_was_written_before_cleaning(self):
        """
        GIVEN a participant whose name was written with extra spaces and angle brackets
        WHEN a text holds the name as written
        THEN it is replaced whole
        """
        roster = _roster(_opinion("Jan   <Nov\u00e1k>"))

        assert mask_participants("Jan   <Nov\u00e1k> spoke", roster) == "Expert 1 spoke"

    def test_a_name_stored_in_lower_case_is_found_when_written_with_a_capital(self):
        """
        GIVEN a participant whose name was stored in lower case
        WHEN a text writes it with capitals
        THEN it is replaced
        """
        roster = _roster(_opinion("jan nov\u00e1k"))

        assert mask_participants("Jan Nov\u00e1k", roster) == "Expert 1"

    def test_other_dashes_join_the_parts_of_a_name(self):
        """
        GIVEN a participant with a hyphenated surname
        WHEN a text joins the parts with an en dash
        THEN the whole name is replaced as one
        """
        roster = _roster(_opinion("Jana Nov\u00e1kov\u00e1-Svobodov\u00e1"))

        assert mask_participants("Jana Nov\u00e1kov\u00e1\u2013Svobodov\u00e1", roster) == (
            "Expert 1"
        )


class TestEveryWayAParticipantIsWritten:
    """A participant is found whichever way round the name is written, and however it is made."""

    @pytest.mark.parametrize("text", ["Jan", "Nov\u00e1k", "Nov\u00e1k Jan", "Jan Nov\u00e1k"])
    def test_a_first_name_alone_or_a_reversed_name_is_found(self, text):
        """
        GIVEN a participant named Jan Novák
        WHEN a text holds the first name alone, the surname alone, or the name reversed
        THEN every word of it is replaced
        """
        roster = _roster(_opinion("Jan Nov\u00e1k"))

        result = mask_participants(f"Ask {text} now", roster)

        assert "Jan" not in result
        assert "Nov\u00e1k" not in result
        assert result.startswith("Ask Expert 1")

    def test_a_name_with_regex_symbols_is_found_literally(self):
        """
        GIVEN participants whose name and position are full of regex symbols
        WHEN a text holds them, and a text holds only what the symbols would stand for
        THEN the first is replaced and the second is not
        """
        roster = _roster(_opinion("A.* (B)+ [x]", "R&D (head)+ ^$"))

        assert mask_participants("A.* (B)+ [x] and R&D (head)+ ^$", roster) == (
            "Expert 1 and [position of Expert 1]"
        )
        assert mask_participants("Axyz BB x", roster) == "Axyz BB x"

    def test_a_name_made_of_short_parts_is_found_whole(self):
        """
        GIVEN participants named J K and J Novák
        WHEN a text holds the names and the lone letter J
        THEN the names are replaced whole and the lone J is not
        """
        roster = _roster(_opinion("J K"), _opinion("J Nov\u00e1k"))

        assert mask_participants("J K and J Nov\u00e1k and J", roster) == (
            "Expert 1 and Expert 2 and J"
        )

    def test_a_name_in_a_script_without_spaces_is_found_inside_a_run_of_text(self):
        """
        GIVEN a participant whose name is written in Chinese characters
        WHEN a text holds the name with other characters on both sides
        THEN it is replaced
        """
        roster = _roster(_opinion("\u738b\u4f1f"))

        assert mask_participants("\u8bf7\u95ee\u738b\u4f1f\u8bf4", roster) == (
            "\u8bf7\u95ee" + "Expert 1" + "\u8bf4"
        )

    @pytest.mark.parametrize(
        "text",
        ["\uff2e\uff4f\uff56\u00e1\uff4b", "Nov\u200b\u00e1k", "Nov\u00ad\u00e1k", "Nova\u0301k"],
        ids=["full-width", "zero-width space", "soft hyphen", "combining accent"],
    )
    def test_compatibility_forms_and_invisible_characters_do_not_hide_a_name(self, text):
        """
        GIVEN a participant named Novák
        WHEN a text spells it with full-width letters, an invisible character or a combining
            accent
        THEN it is replaced
        """
        roster = _roster(_opinion("Nov\u00e1k"))

        assert mask_participants(f"Ask {text}.", roster) == "Ask Expert 1."

    def test_a_pattern_that_cannot_be_built_raises_instead_of_returning_the_text(self):
        """
        GIVEN a roster whose pattern fails to build
        WHEN a text is masked
        THEN the failure reaches the caller, and the text does not come back as it was
        """
        roster = _roster(_opinion("Alice Moore"))

        with patch.object(TurnRoster, "_build", side_effect=re.error("too big")):
            with pytest.raises(re.error):
                mask_participants("Alice Moore", roster)
            with pytest.raises(re.error):
                label_known_rows("- Alice Moore: lower=1.00", roster)


class TestWhatIsNotAName:
    """Nothing is replaced that is a symbol, a layout word or an earlier replacement."""

    def test_the_escape_of_a_line_break_in_a_name_is_not_searched_for(self):
        """
        GIVEN a participant whose name holds a typed backslash and n
        WHEN a repr-style text with escaped line breaks is masked
        THEN the line breaks stay
        """
        roster = _roster(_opinion("Zed \\n Smith"))

        assert mask_participants("one\\ntwo", roster) == "one\\ntwo"

    def test_a_position_made_of_symbols_is_not_searched_for(self):
        """
        GIVEN participants whose positions are a dash and a pair of brackets
        WHEN a text with dashes and brackets is masked
        THEN it is unchanged
        """
        roster = _roster(_opinion("Alice Moore", "-"), _opinion("Bob Green", "()"))

        assert mask_participants("a - b (c)", roster) == "a - b (c)"

    def test_a_label_already_in_a_text_is_not_rewritten_by_a_name(self):
        """
        GIVEN a participant named Expert Kowalski, who is Expert 2
        WHEN a text already holds Expert 1 and the name
        THEN the label stays and the name becomes Expert 2
        """
        roster = _roster(_opinion("Alice Moore"), _opinion("Expert Kowalski"))

        assert mask_participants("Expert 1 and Expert Kowalski", roster) == (
            "Expert 1 and Expert 2"
        )

    @pytest.mark.parametrize("layout_word", ["Number", "lower", "opinions", "centroid"])
    def test_a_name_that_is_a_word_of_the_block_layout_cannot_hide_other_rows(self, layout_word):
        """
        GIVEN a participant named after a word of the block layout, and a block that also
            holds an expert the roster never met
        WHEN the block is masked
        THEN the unknown expert's row loses its name all the same
        """
        roster = _roster(_opinion(layout_word))
        block = render_opinions([_opinion(layout_word), _opinion("Stranger Unknown")])

        masked = _hide(block, roster)

        assert "Stranger" not in masked
        assert "Unknown" not in masked
        assert masked.count("37.00") == 2


class TestPositions:
    """A position is found as a whole phrase, never word by word."""

    def test_a_position_is_replaced_with_the_holders_label(self):
        """
        GIVEN a participant with a multi-word position
        WHEN a text holds the position, in other case
        THEN it becomes a placeholder naming the holder
        """
        roster = _roster(_opinion("Alice Moore", "Dam Safety Officer at Lipno"))

        text = "She is a dam safety officer at Lipno."
        assert mask_participants(text, roster) == "She is a [position of Expert 1]."

    def test_the_words_of_a_position_survive_in_ordinary_text(self):
        """
        GIVEN a participant with a multi-word position
        WHEN a text uses the position's words one by one
        THEN none of them is replaced
        """
        roster = _roster(_opinion("Alice Moore", "Dam Safety Officer at Lipno"))

        text = "The officer checked safety at the dam."
        assert mask_participants(text, roster) == text

    def test_a_position_shared_by_several_participants_is_not_attributed(self):
        """
        GIVEN two participants with the same position
        WHEN a text holds it
        THEN the placeholder names no one
        """
        roster = _roster(_opinion("Alice Moore"), _opinion("Bob Green"))

        assert mask_participants("A Hydrologist spoke.", roster) == "A [position] spoke."

    def test_a_position_is_found_in_other_cases(self):
        """
        GIVEN a participant whose position is two words
        WHEN a text holds the position with each word declined
        THEN it is replaced
        """
        roster = _roster(_opinion("Alice Moore", "Vedoucí odboru"))

        text = "Rozhodl vedoucí odboru."
        assert mask_participants(text, roster) == "Rozhodl [position of Expert 1]."

    def test_a_name_inside_the_position_is_still_one_phrase(self):
        """
        GIVEN a participant whose position contains a word that is another participant's name
        WHEN the position is in a text
        THEN the position is replaced as a whole, and the label is not read again
        """
        roster = _roster(_opinion("Alice Moore", "Assistant to Bob"), _opinion("Bob Green"))

        result = mask_participants("Alice is Assistant to Bob", roster)

        assert result == "Expert 1 is [position of Expert 1]"


class TestBlockRows:
    """A row of an opinions block takes the label of the roster, with the position dropped."""

    def test_a_known_row_is_labelled_from_the_roster(self):
        """
        GIVEN a block of two opinions, and a roster that met them in the other order
        WHEN the block is masked with the roster
        THEN each row carries its participant's label, the position is not in the block,
            and the numbers stay
        """
        alice, bob = _opinion("Alice Moore", "Hydrologist"), _opinion("Bob Green", "Chair")
        roster = _roster(bob, alice)

        masked = mask_participants(render_opinions([alice, bob]), roster)

        assert "- Expert 2: lower=37.00" in masked
        assert "- Expert 1: lower=37.00" in masked
        assert masked.index("Expert 2") < masked.index("Expert 1")
        assert "Alice" not in masked
        assert "Hydrologist" not in masked

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
        WHEN it is masked with the roster and then by shape
        THEN the rows carry the roster's labels and no name is left
        """
        alice, bob = _opinion("Alice Moore"), _opinion("Bob Green")
        roster = _roster(bob, alice)
        error = repr(ValueError(render_opinions([alice, bob])))

        masked = _hide(error, roster)

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
