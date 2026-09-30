"""Tests for the citation and number grounding checks."""

import pytest

from api.assistant.agent.checks import check_citations, find_ungrounded_numbers

# Every citation-like form, with the numbers it names.
_CITATION_FORMS = [
    ("[1]", {1}),
    ("[1, 2]", {1, 2}),
    ("[1,2]", {1, 2}),
    ("[1; 2]", {1, 2}),
    ("[1 2]", {1, 2}),
    ("[1-3]", {1, 2, 3}),
    ("[1\u20133]", {1, 2, 3}),
    ("[1 - 3]", {1, 2, 3}),
    ("[1, 3-5]", {1, 3, 4, 5}),
    ("[Source 1]", {1}),
    ("[Source: 2]", {2}),
    ("[Source #3]", {3}),
    ("[Source \u21163]", {3}),
    ("[Zdroj.4]", {4}),
    ("[doc1]", {1}),
    ("[\u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a 2]", {2}),
    ("\u30101\u3011", {1}),
    ("\u30101, 2\u3011", {1, 2}),
    ("[12]", {12}),
    ("[123]", {123}),
]

_EACH_FORM = pytest.mark.parametrize(("form", "named"), _CITATION_FORMS)


class TestCheckCitations:
    """Every citation in the answer must name a source that was actually given."""

    def test_true_when_the_answer_has_no_citations(self):
        """
        GIVEN an answer without a citation
        WHEN the citations are checked
        THEN the answer passes
        """
        assert check_citations("The method combines a mean and a median.", {1, 2}) is True

    def test_true_when_every_citation_is_valid(self):
        """
        GIVEN an answer citing sources 1 and 2, both given
        WHEN the citations are checked
        THEN the answer passes
        """
        assert check_citations("See [1] and [2].", {1, 2}) is True

    def test_false_when_a_citation_was_not_given(self):
        """
        GIVEN an answer citing source 3, which was never given
        WHEN the citations are checked
        THEN the answer fails
        """
        assert check_citations("See [3].", {1, 2}) is False

    @_EACH_FORM
    def test_reads_every_citation_like_form(self, form: str, named: set[int]):
        """
        GIVEN a citation written in one of the accepted forms
        WHEN the citations are checked against exactly the numbers it names
        THEN it passes, and it fails when the sources given are none
        """
        answer = f"The mean is used {form}."

        assert check_citations(answer, named) is True
        assert check_citations(answer, set()) is False

    def test_expands_a_range(self):
        """
        GIVEN the citation [1-3]
        WHEN source 2, inside the range, was never given
        THEN the answer fails
        """
        assert check_citations("See [1-3].", {1, 3}) is False
        assert check_citations("See [1-3].", {1, 2, 3}) is True

    def test_expands_an_en_dash_range(self):
        """
        GIVEN the citation [1-3] written with an en dash
        WHEN source 2, inside the range, was never given
        THEN the answer fails
        """
        assert check_citations("See [1\u20133].", {1, 3}) is False

    def test_source_zero_is_never_valid(self):
        """
        GIVEN the citation [0]
        WHEN the sources given are numbered from one
        THEN the answer fails
        """
        assert check_citations("See [0].", {1, 2}) is False

    def test_a_bracket_holding_decimals_is_not_a_citation(self):
        """
        GIVEN a bracket with decimal numbers
        WHEN the citations are checked with no sources at all
        THEN the answer passes, because the bracket is not a citation
        """
        assert check_citations("The range is [11.54, 14.19].", set()) is True

    def test_a_bracket_of_four_digits_is_not_a_citation(self):
        """
        GIVEN the bracket [2024]
        WHEN the citations are checked with no sources at all
        THEN the answer passes
        """
        assert check_citations("Published [2024].", set()) is True

    def test_a_bracket_of_words_is_not_a_citation(self):
        """
        GIVEN a bracket with no number in it
        WHEN the citations are checked with no sources at all
        THEN the answer passes
        """
        assert check_citations("Use the [Results] page.", set()) is True

    def test_a_markdown_link_counts_as_its_citation(self):
        """
        GIVEN the markdown link [3](https://becomify.app/docs)
        WHEN source 3 was never given
        THEN the answer fails, and it passes when source 3 was given
        """
        answer = "See [3](https://becomify.app/docs)."

        assert check_citations(answer, {1}) is False
        assert check_citations(answer, {3}) is True


class TestFindUngroundedNumbers:
    """A number must be backed by a grounding text, or it is flagged."""

    def test_no_numbers_in_the_answer_means_nothing_ungrounded(self):
        """
        GIVEN an answer without numbers
        WHEN the numbers are checked
        THEN nothing is flagged
        """
        assert find_ungrounded_numbers("The panel disagreed.", ["some text"]) == []

    def test_a_grounded_number_is_not_flagged(self):
        """
        GIVEN an answer number that the grounding text states
        WHEN the numbers are checked
        THEN nothing is flagged
        """
        answer = "The best compromise is 14.31 percent."
        grounding = ["The best compromise centroid is 14.31."]

        assert find_ungrounded_numbers(answer, grounding) == []

    def test_an_invented_number_is_flagged(self):
        """
        GIVEN an answer number that the grounding text does not state
        WHEN the numbers are checked
        THEN it is flagged as written
        """
        answer = "The best compromise is 99.99 percent."
        grounding = ["The best compromise centroid is 14.31."]

        assert find_ungrounded_numbers(answer, grounding) == ["99.99"]

    def test_trailing_zeros_do_not_cause_a_false_positive(self):
        """
        GIVEN 5.9700 in the answer and 5.97 in the grounding
        WHEN the numbers are checked
        THEN nothing is flagged
        """
        assert find_ungrounded_numbers("Delta max is 5.9700.", ["Maximum error: 5.97"]) == []

    def test_a_number_from_the_question_is_grounded_when_passed(self):
        """
        GIVEN a number the user wrote, passed as grounding
        WHEN the answer repeats it
        THEN nothing is flagged
        """
        assert find_ungrounded_numbers("With 7 experts...", ["We have 7 experts"]) == []

    @_EACH_FORM
    def test_citation_like_brackets_are_not_numbers(self, form: str, named: set[int]):
        """
        GIVEN a citation in one of the accepted forms
        WHEN the numbers are checked against a grounding with no digits
        THEN its digits are not flagged
        """
        assert named
        assert find_ungrounded_numbers(f"See {form} for the formula.", ["no digits"]) == []

    def test_a_decimal_in_square_brackets_is_still_checked(self):
        """
        GIVEN a bracket holding two decimals, one of them in the grounding
        WHEN the numbers are checked
        THEN the other is flagged
        """
        answer = "The range is [11.54, 14.19]."

        assert find_ungrounded_numbers(answer, ["lower 11.54"]) == ["14.19"]

    def test_a_bracket_of_four_digits_is_still_checked(self):
        """
        GIVEN the bracket [2024] and a grounding without it
        WHEN the numbers are checked
        THEN 2024 is flagged
        """
        assert find_ungrounded_numbers("Published [2024].", ["nothing"]) == ["2024"]

    def test_list_numbering_is_not_a_number(self):
        """
        GIVEN a numbered list and a grounding with no digits
        WHEN the numbers are checked
        THEN the item numbers are not flagged
        """
        answer = "Steps:\n1. Collect opinions\n2) Run the calculation\n  3. Read the result"

        assert find_ungrounded_numbers(answer, ["no digits"]) == []

    def test_a_number_at_the_start_of_a_line_is_still_checked(self):
        """
        GIVEN a line that opens with a decimal rather than a list marker
        WHEN the numbers are checked against a grounding without it
        THEN the decimal is flagged
        """
        assert find_ungrounded_numbers("5.97 was the error", ["nothing"]) == ["5.97"]

    def test_the_url_of_a_markdown_link_is_not_read(self):
        """
        GIVEN a markdown link whose target holds digits
        WHEN the numbers are checked
        THEN the target's digits are not flagged, while the link text still is
        """
        answer = "See [the 2024 docs](https://becomify.app/docs/v12/page5)."

        assert find_ungrounded_numbers(answer, ["nothing"]) == ["2024"]

    def test_the_relative_target_of_a_markdown_link_is_not_read(self):
        """
        GIVEN a markdown link whose target is a relative path with digits
        WHEN the numbers are checked
        THEN the target's digits are not flagged
        """
        answer = "See [the docs](/docs/v12/page5) and [this step](#step-3)."

        assert find_ungrounded_numbers(answer, ["nothing"]) == []

    def test_a_markdown_citation_link_is_not_read(self):
        """
        GIVEN a citation written as a markdown link
        WHEN the numbers are checked
        THEN neither the citation nor the target is flagged
        """
        answer = "See [1](https://becomify.app/docs/v12/page5)."

        assert find_ungrounded_numbers(answer, ["nothing"]) == []

    def test_a_bare_url_is_not_read(self):
        """
        GIVEN a bare URL with digits in it
        WHEN the numbers are checked
        THEN the URL's digits are not flagged
        """
        answer = "Visit https://becomify.app/docs/step-3/12345 now, or http://example.org/7."

        assert find_ungrounded_numbers(answer, ["nothing"]) == []

    def test_a_token_next_to_a_letter_or_underscore_is_not_a_number(self):
        """
        GIVEN model names, ids and ordinals with digits in them
        WHEN the numbers are checked
        THEN none is flagged
        """
        answer = "Qwen3 and doc1 and 1st and H2O and 20px and a_5 and 5_b and \u010d7"

        assert find_ungrounded_numbers(answer, ["nothing"]) == []

    def test_a_number_beside_punctuation_is_a_number(self):
        """
        GIVEN numbers next to a percent sign, a full stop and brackets
        WHEN the numbers are checked
        THEN each is flagged without the punctuation
        """
        answer = "It is 20%, or 14.19. Also (5.97)."

        assert find_ungrounded_numbers(answer, ["nothing"]) == ["20", "14.19", "5.97"]

    def test_a_minus_at_the_start_of_the_text_is_a_sign(self):
        """
        GIVEN -5 at the very start of the answer
        WHEN the grounding only has 5
        THEN -5 is flagged with its sign
        """
        assert find_ungrounded_numbers("-5 is low", ["5"]) == ["-5"]

    def test_a_minus_after_whitespace_is_a_sign(self):
        """
        GIVEN -5 after a space
        WHEN the grounding only has 5
        THEN -5 is flagged with its sign
        """
        assert find_ungrounded_numbers("it is -5", ["5"]) == ["-5"]

    def test_a_minus_after_an_opening_bracket_is_a_sign(self):
        """
        GIVEN -5 after an opening bracket
        WHEN the grounding only has 5, and then when it has -5
        THEN -5 is flagged, and then it is not
        """
        assert find_ungrounded_numbers("it is (-5)", ["5"]) == ["-5"]
        assert find_ungrounded_numbers("it is (-5)", ["-5"]) == []

    def test_a_hyphen_between_numbers_is_a_range(self):
        """
        GIVEN the range 20-40
        WHEN the grounding has 20 and 40
        THEN nothing is flagged, because it is two numbers and no minus sign
        """
        assert find_ungrounded_numbers("Between 20-40 percent", ["20 and 40"]) == []

    def test_an_en_dash_between_numbers_is_a_range(self):
        """
        GIVEN the range 20 to 40 written with an en dash
        WHEN the grounding has 20 and 40
        THEN nothing is flagged
        """
        assert find_ungrounded_numbers("Between 20\u201340 percent", ["20 and 40"]) == []

    def test_the_unicode_minus_is_a_sign(self):
        """
        GIVEN a number written with the Unicode minus
        WHEN the grounding has -5, and then when it only has 5
        THEN it is grounded, and then flagged as written
        """
        assert find_ungrounded_numbers("It is \u22125", ["-5"]) == []
        assert find_ungrounded_numbers("It is \u22125", ["5"]) == ["\u22125"]

    @pytest.mark.parametrize("space", [" ", "\u00a0", "\u202f"])
    def test_space_grouped_thousands_are_one_number(self, space: str):
        """
        GIVEN 1 000 written with one of the three space characters
        WHEN the grounding states 1000, and then only 1 and 0
        THEN it is grounded, and then flagged as one number
        """
        written = f"1{space}000"

        assert find_ungrounded_numbers(f"About {written} people", ["total: 1000"]) == []
        assert find_ungrounded_numbers(f"About {written} people", ["1 and 0"]) == [written]

    def test_space_grouped_thousands_with_a_decimal_comma(self):
        """
        GIVEN 1 000,5
        WHEN the grounding states 1000.5
        THEN nothing is flagged
        """
        assert find_ungrounded_numbers("It is 1 000,5 units", ["value 1000.5"]) == []

    def test_a_group_of_four_digits_is_not_a_thousands_group(self):
        """
        GIVEN 1 0000
        WHEN the grounding has 1 and 0000
        THEN nothing is flagged, because it is two numbers
        """
        assert find_ungrounded_numbers("It is 1 0000", ["1 and 0000"]) == []

    def test_comma_thousands_with_a_dot_decimal_are_one_number(self):
        """
        GIVEN 1,234.56
        WHEN the grounding states 1234.56, and then only 1 and 234.56
        THEN it is grounded, and then flagged as one number
        """
        assert find_ungrounded_numbers("It is 1,234.56", ["1234.56"]) == []
        assert find_ungrounded_numbers("It is 1,234.56", ["1 and 234.56"]) == ["1,234.56"]

    def test_a_czech_decimal_comma_reads_as_a_decimal(self):
        """
        GIVEN 14,19
        WHEN the grounding states 14.19
        THEN nothing is flagged
        """
        assert find_ungrounded_numbers("It is 14,19", ["peak 14.19"]) == []

    def test_a_comma_list_is_grounded_by_its_members(self):
        """
        GIVEN (6,8,11)
        WHEN the grounding states 6, 8 and 11, and then only 6 and 8
        THEN it is grounded, and then flagged as written
        """
        assert find_ungrounded_numbers("Values (6,8,11)", ["6 8 11"]) == []
        assert find_ungrounded_numbers("Values (6,8,11)", ["6 8"]) == ["6,8,11"]

    def test_comma_thousands_are_grounded_by_the_whole_number(self):
        """
        GIVEN 1,234
        WHEN the grounding states 1234, and then only 1 and 234
        THEN it is grounded both times, and it is flagged when neither reading holds
        """
        assert find_ungrounded_numbers("It is 1,234", ["1234"]) == []
        assert find_ungrounded_numbers("It is 1,234", ["1 and 234"]) == []
        assert find_ungrounded_numbers("It is 1,234", ["1 and 235"]) == ["1,234"]

    def test_a_number_the_data_rounds_to_is_grounded(self):
        """
        GIVEN 14.1923076923 in the data
        WHEN the answer says 14.19, 14.2 or 14
        THEN nothing is flagged, but 15 is
        """
        grounding = ["Best compromise: peak=14.1923076923"]

        assert find_ungrounded_numbers("It is 14.19", grounding) == []
        assert find_ungrounded_numbers("It is 14.2", grounding) == []
        assert find_ungrounded_numbers("It is 14", grounding) == []
        assert find_ungrounded_numbers("It is 15", grounding) == ["15"]

    def test_a_number_the_data_truncates_to_is_grounded(self):
        """
        GIVEN 5.9789 in the data
        WHEN the answer says 5.97 (truncated) or 5.98 (rounded)
        THEN nothing is flagged, but 5.96 is
        """
        grounding = ["Maximum error: 5.9789"]

        assert find_ungrounded_numbers("It is 5.97", grounding) == []
        assert find_ungrounded_numbers("It is 5.98", grounding) == []
        assert find_ungrounded_numbers("It is 5.96", grounding) == ["5.96"]

    def test_a_tie_rounds_half_up(self):
        """
        GIVEN 2.5 in the data
        WHEN the answer says 3
        THEN nothing is flagged
        """
        assert find_ungrounded_numbers("It is 3", ["value 2.5"]) == []

    def test_precision_beyond_a_float_is_kept(self):
        """
        GIVEN a value with 27 significant digits in the data
        WHEN the answer quotes it to two decimals
        THEN nothing is flagged, and a different value with the same float is
        """
        grounding = ["123456789012345678.123456789"]

        assert find_ungrounded_numbers("It is 123456789012345678.12", grounding) == []
        assert find_ungrounded_numbers("It is 123456789012345678.99", grounding) == [
            "123456789012345678.99"
        ]

    def test_a_percentage_is_compared_as_written(self):
        """
        GIVEN 20 % in the answer
        WHEN the grounding only has 0.2
        THEN 20 is flagged
        """
        assert find_ungrounded_numbers("About 20 % agree", ["share 0.2"]) == ["20"]

    def test_a_grounding_token_next_to_a_letter_grounds_nothing(self):
        """
        GIVEN a grounding that only mentions Qwen3
        WHEN the answer says 3
        THEN 3 is flagged
        """
        assert find_ungrounded_numbers("It is 3", ["the Qwen3 model"]) == ["3"]

    def test_each_number_is_reported_once_in_order_of_first_appearance(self):
        """
        GIVEN repeated ungrounded numbers
        WHEN the numbers are checked
        THEN each comes back once, in the order it first appeared
        """
        answer = "9, 7, 9, 3, 7"

        assert find_ungrounded_numbers(answer, ["nothing"]) == ["9", "7", "3"]

    def test_an_english_triplet_is_read_number_by_number(self):
        """
        GIVEN (11.54, 14.19, 17.19) and a grounding that lacks the last
        WHEN the numbers are checked
        THEN only the last is flagged
        """
        answer = "The compromise is (11.54, 14.19, 17.19)."

        assert find_ungrounded_numbers(answer, ["11.54 and 14.19"]) == ["17.19"]

    def test_a_czech_triplet_is_read_number_by_number(self):
        """
        GIVEN (11,54; 14,19; 17,19) and a grounding written with dots
        WHEN the numbers are checked
        THEN nothing is flagged, and the last is flagged once it is missing
        """
        answer = "Kompromis je (11,54; 14,19; 17,19)."

        assert find_ungrounded_numbers(answer, ["11.54 14.19 17.19"]) == []
        assert find_ungrounded_numbers(answer, ["11.54 14.19"]) == ["17,19"]
