"""Tests for the citation and number grounding checks."""

import pytest

from api.assistant.agent.checks import check_citations, find_ungrounded_numbers, strip_citations

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

    @pytest.mark.parametrize(
        "answer",
        [
            "See [see the formula](method.md#step-3).",
            "See [the guide](guide2.md).",
            "See [1](doc1).",
        ],
    )
    def test_a_bare_relative_link_target_is_not_read(self, answer: str):
        """
        GIVEN a markdown link whose target is a bare relative file with digits
        WHEN the numbers are checked
        THEN the target's digits are not flagged
        """
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

    @pytest.mark.parametrize(
        "line",
        [
            "(1) first",
            "**1.** Compute the mean",
            "- 2) item",
            "### 3. Result",
            "> 4. quoted",
            "* _5._ emphasised",
            "  - (6) nested",
        ],
    )
    def test_decorated_list_numbering_is_not_a_number(self, line: str):
        """
        GIVEN a list item numbered with brackets or behind markdown decoration
        WHEN the numbers are checked against a grounding with no digits
        THEN the item number is not flagged
        """
        assert find_ungrounded_numbers(f"Steps:\n{line}", ["no digits"]) == []

    def test_an_ordinal_inside_a_sentence_is_not_a_number(self):
        """
        GIVEN a Czech ordinal (a number, a dot, a lowercase word)
        WHEN the numbers are checked against a grounding with no digits
        THEN the ordinal is not flagged
        """
        assert find_ungrounded_numbers("Ve 2. kroku se pocita mediana.", ["nothing"]) == []

    def test_an_ordinal_before_a_lowercase_letter_with_a_diacritic(self):
        """
        GIVEN an ordinal followed by a lowercase letter with a diacritic
        WHEN the numbers are checked
        THEN the ordinal is not flagged
        """
        answer = "Ve 3. \N{LATIN SMALL LETTER C WITH CARON}ast"

        assert find_ungrounded_numbers(answer, ["nothing"]) == []

    def test_a_number_that_ends_a_sentence_is_still_checked(self):
        """
        GIVEN an ungrounded number followed by a full stop and a capital
        WHEN the numbers are checked
        THEN the number is reported
        """
        answer = "The count is 13. The panel agreed."

        assert find_ungrounded_numbers(answer, ["nothing"]) == ["13"]

    def test_a_number_that_ends_a_sentence_before_a_capital_with_a_diacritic(self):
        """
        GIVEN an ungrounded number, a full stop, and a capital letter with a diacritic
        WHEN the numbers are checked
        THEN the number is reported
        """
        answer = "The count is 13. \N{LATIN CAPITAL LETTER C WITH CARON}ast two."

        assert find_ungrounded_numbers(answer, ["nothing"]) == ["13"]

    def test_three_digits_and_a_dot_are_not_an_ordinal(self):
        """
        GIVEN a three-digit number, a full stop, and a lowercase word
        WHEN the numbers are checked
        THEN the number is reported
        """
        assert find_ungrounded_numbers("It is 123. and so on", ["nothing"]) == ["123"]

    @pytest.mark.parametrize(
        "token",
        ["v1.2.3", "Qwen3.5", "Qwen3.5-9B", "doc1", "1st", "H2O", "Python3.13.7"],
    )
    def test_a_token_mixing_letters_and_digits_is_dropped_whole(self, token: str):
        """
        GIVEN a version, a model name or an identifier with a dot-joined digit tail
        WHEN the numbers are checked against a grounding with no digits
        THEN no part of it is flagged
        """
        assert find_ungrounded_numbers(f"We used {token} here.", ["nothing"]) == []

    def test_a_decimal_next_to_a_unit_is_not_read_in_pieces(self):
        """
        GIVEN a decimal glued to a unit
        WHEN the numbers are checked
        THEN neither the integer nor the fraction part is flagged
        """
        assert find_ungrounded_numbers("It is 8.5mm wide.", ["nothing"]) == []

    @pytest.mark.parametrize(
        "date",
        ["2026-09-29", "29.09.2026", "29. 9. 2026", "1.10.2025"],
    )
    def test_a_date_is_not_a_number(self, date: str):
        """
        GIVEN a date written in ISO or dotted form
        WHEN the numbers are checked against a grounding with no digits
        THEN no part of the date is flagged
        """
        assert find_ungrounded_numbers(f"Calculated on {date} by the panel.", ["nothing"]) == []

    def test_a_minus_after_an_equals_sign_is_a_sign(self):
        """
        GIVEN the project block's ``lower=-2.50``
        WHEN the answer says -2.5, and then 2.5
        THEN -2.5 is grounded and 2.5 is not
        """
        grounding = ["Median: lower=-2.50, peak=1.00"]

        assert find_ungrounded_numbers("The lower bound is -2.5.", grounding) == []
        assert find_ungrounded_numbers("The lower bound is 2.5.", grounding) == ["2.5"]


class TestStripCitations:
    """Citation-like brackets can be removed from a text on their own."""

    @_EACH_FORM
    def test_removes_every_citation_like_form(self, form: str, named: set[int]):
        """
        GIVEN a citation in one of the accepted forms
        WHEN citations are stripped
        THEN the words around it remain and it does not
        """
        assert named
        assert strip_citations(f"The mean {form} is used.").split() == [
            "The",
            "mean",
            "is",
            "used.",
        ]

    def test_removes_the_link_target_that_follows_a_citation(self):
        """
        GIVEN a citation written as a markdown link
        WHEN citations are stripped
        THEN the target goes with it
        """
        assert strip_citations("See [1](https://becomify.app/docs) now").split() == ["See", "now"]

    def test_keeps_a_parenthesis_that_is_not_a_link_target(self):
        """
        GIVEN a citation followed by a space and a parenthesis
        WHEN citations are stripped
        THEN the parenthesis stays
        """
        assert strip_citations("Result [1] (5 experts)").split() == ["Result", "(5", "experts)"]

    def test_keeps_a_bracket_that_is_not_a_citation(self):
        """
        GIVEN a bracket holding decimals
        WHEN citations are stripped
        THEN the text is unchanged
        """
        text = "The range is [11.54, 14.19]."

        assert strip_citations(text) == text

    def test_a_text_without_brackets_is_unchanged(self):
        """
        GIVEN a text without brackets
        WHEN citations are stripped
        THEN the text is unchanged
        """
        assert strip_citations("No brackets, 5 experts.") == "No brackets, 5 experts."


class TestSignsAfterSeparators:
    """A minus after a comma, a semicolon or a colon is a sign."""

    @pytest.mark.parametrize(
        "answer",
        ["The bounds are (-5,-3).", "The peak:-3 is low.", "It is [-5.5,-3.5].", "Set 1;-3 now"],
    )
    def test_a_minus_after_a_separator_is_a_sign(self, answer: str):
        """
        GIVEN negative numbers written right after a comma, a colon or a semicolon
        WHEN the grounding states them with their signs
        THEN nothing is flagged
        """
        grounding = ["-5 -3 -5.5 -3.5 1"]

        assert find_ungrounded_numbers(answer, grounding) == []

    def test_the_same_numbers_without_signs_are_not_grounded_by_negatives(self):
        """
        GIVEN a grounding that only has negative values
        WHEN the answer says the positive ones after a separator
        THEN they are flagged
        """
        assert find_ungrounded_numbers("It is (5,3).", ["-5 -3"]) == ["5,3"]


class TestCompactLists:
    """Comma-joined elements may carry a dot decimal."""

    def test_a_compact_list_with_a_dot_decimal_is_read_element_by_element(self):
        """
        GIVEN (6,8.75,11)
        WHEN the grounding states 6, 8.75 and 11
        THEN nothing is flagged
        """
        assert find_ungrounded_numbers("Values (6,8.75,11)", ["6 8.75 11"]) == []

    def test_a_compact_pair_with_a_dot_decimal(self):
        """
        GIVEN 5,3.5
        WHEN the grounding states 5 and 3.5, and then 5.3 and 5
        THEN it is grounded, and then flagged as written
        """
        assert find_ungrounded_numbers("Pair 5,3.5", ["5 3.5"]) == []
        assert find_ungrounded_numbers("Pair 5,3.5", ["5.3 5"]) == ["5,3.5"]

    def test_a_compact_list_with_a_dot_decimal_is_not_a_decimal_comma(self):
        """
        GIVEN 5,3.5, which no single number can be
        WHEN the grounding states only 7 and 3.5
        THEN it is flagged, because the element 5 is missing
        """
        assert find_ungrounded_numbers("Pair 5,3.5", ["7 3.5"]) == ["5,3.5"]


class TestSpaceGroupedLists:
    """Space-separated groups of three digits can be a list as well as one number."""

    def test_three_hundreds_are_grounded_by_their_members(self):
        """
        GIVEN (100 200 300)
        WHEN the grounding states 100, 200 and 300 separately
        THEN nothing is flagged
        """
        assert find_ungrounded_numbers("Values (100 200 300)", ["100, 200, 300"]) == []

    def test_a_thousand_is_still_grounded_by_the_whole_number(self):
        """
        GIVEN 1 000
        WHEN the grounding states 1000
        THEN nothing is flagged
        """
        assert find_ungrounded_numbers("It is 1 000", ["1000"]) == []

    def test_a_group_list_with_a_missing_member_is_flagged(self):
        """
        GIVEN (100 200 300)
        WHEN the grounding lacks 300 and is not their concatenation
        THEN the token is flagged
        """
        assert find_ungrounded_numbers("Values (100 200 300)", ["100 200"]) == ["100 200 300"]


class TestOrdinalsStayOnOneLine:
    """An ordinal's whitespace does not cross a line break."""

    def test_a_number_ending_a_line_before_a_lowercase_line_is_still_checked(self):
        """
        GIVEN "8." at the end of a line and a lowercase word on the next
        WHEN the grounding has no 8
        THEN 8 is reported
        """
        assert find_ungrounded_numbers("The median is 8.\nthe next", ["nothing"]) == ["8"]

    @pytest.mark.parametrize("gap", [" ", "\t", "\xa0", "\N{NARROW NO-BREAK SPACE}"])
    def test_a_space_tab_or_no_break_space_still_makes_an_ordinal(self, gap: str):
        """
        GIVEN an ordinal followed by a space, a tab or a no-break space
        WHEN the numbers are checked
        THEN it is not flagged
        """
        assert find_ungrounded_numbers(f"Ve 2.{gap}kroku", ["nothing"]) == []


class TestCompoundNames:
    """A digit run after letters and a hyphen belongs to a name."""

    @pytest.mark.parametrize("name", ["COVID-19", "GPT-4", "ISO-8601", "SARS-2.1"])
    def test_a_name_with_a_hyphenated_number_is_not_a_number(self, name: str):
        """
        GIVEN a name such as COVID-19
        WHEN the numbers are checked against a grounding with no digits
        THEN nothing is flagged
        """
        assert find_ungrounded_numbers(f"Data on {name} cases", ["nothing"]) == []

    def test_a_range_of_numbers_is_still_a_range(self):
        """
        GIVEN 20-40
        WHEN the grounding has 20 and 40
        THEN nothing is flagged, and 40 is flagged when it is missing
        """
        assert find_ungrounded_numbers("Between 20-40", ["20 and 40"]) == []
        assert find_ungrounded_numbers("Between 20-40", ["20"]) == ["40"]

    def test_a_negative_after_a_space_is_still_negative(self):
        """
        GIVEN "x = -3" and "(-5)"
        WHEN the grounding only has 3 and 5
        THEN the signed numbers are flagged
        """
        assert find_ungrounded_numbers("x = -3", ["3"]) == ["-3"]
        assert find_ungrounded_numbers("(-5)", ["5"]) == ["-5"]


class TestNegativePrecision:
    """A negative value keeps every digit."""

    def test_a_negative_value_beyond_28_digits_is_kept(self):
        """
        GIVEN a negative value with 35 significant digits in the data
        WHEN the answer quotes it to two decimals, and then quotes a nearby value
        THEN the first is grounded and the nearby one is flagged
        """
        grounding = ["value=-1234567890123456789012345678.1234567"]
        exact = "-1234567890123456789012345678.12"
        nearby = "-1234567890123456789012345678.13"

        assert find_ungrounded_numbers(f"It is {exact}", grounding) == []
        assert find_ungrounded_numbers(f"It is {nearby}", grounding) == [nearby]

    def test_a_negative_answer_beyond_28_digits_is_not_rounded_into_the_data(self):
        """
        GIVEN a data value that is the neighbouring whole number
        WHEN the answer quotes a negative value with decimals beyond 28 digits
        THEN it is flagged, not rounded onto the data
        """
        answer = "It is -1234567890123456789012345678.99"

        assert find_ungrounded_numbers(answer, ["-1234567890123456789012345679"]) == [
            "-1234567890123456789012345678.99"
        ]


class TestCitationLabels:
    """Every number in a citation bracket may carry its own label."""

    def test_a_label_before_every_number_is_one_citation(self):
        """
        GIVEN [Source 1, Source 2]
        WHEN only source 1 was given, and then both
        THEN the check fails, and then passes
        """
        assert check_citations("see [Source 1, Source 2]", {1}) is False
        assert check_citations("see [Source 1, Source 2]", {1, 2}) is True

    def test_the_digits_of_a_labelled_list_do_not_reach_the_number_scan(self):
        """
        GIVEN [Source 1, Source 2]
        WHEN the numbers are checked against a grounding with no digits
        THEN nothing is flagged
        """
        assert find_ungrounded_numbers("see [Source 1, Source 2]", ["nothing"]) == []

    def test_a_label_before_a_range_end(self):
        """
        GIVEN [Source 1 - Source 3]
        WHEN source 2 was not given
        THEN the check fails
        """
        assert check_citations("see [Source 1 - Source 3]", {1, 3}) is False

    def test_the_full_width_dagger_form_is_not_read(self):
        """
        GIVEN a full-width bracket holding a number, a dagger and a word
        WHEN the citations are checked with no sources
        THEN it is not seen as a citation (a known limit)
        """
        dagger = chr(0x2020)
        answer = f"see {chr(0x3010)}4{dagger}source{chr(0x3011)}"

        assert check_citations(answer, set()) is True


class TestGuards:
    """Two small guards, pinned."""

    def test_a_citation_inside_a_link_target_after_a_citation_is_not_stripped_twice(self):
        """
        GIVEN a citation whose link target holds another citation-like bracket
        WHEN citations are stripped
        THEN the text around them is intact and nothing is repeated
        """
        assert strip_citations("a [1]([2]) b").split() == ["a", "b"]

    def test_a_reversed_range_names_only_its_two_ends(self):
        """
        GIVEN the reversed range [5-1]
        WHEN sources 1 and 5 were given, and then only 1
        THEN it passes, and then fails (the numbers between the ends are not named)
        """
        assert check_citations("see [5-1]", {1, 5}) is True
        assert check_citations("see [5-1]", {1}) is False


class TestRoundThousandsAreNotInvented:
    """A group that starts with a zero is a thousands group, never a list member."""

    @pytest.mark.parametrize(
        "answer",
        [
            "The panel had 5 000 experts",
            "About 2 000 people",
            "It reached 20 000",
            "A total of 5 000,5 units",
        ],
    )
    def test_a_round_thousand_is_flagged_when_the_data_holds_no_such_number(self, answer: str):
        """
        GIVEN a grounding of small numbers and a decimal below one
        WHEN the answer states a round thousand such as 5 000
        THEN it is flagged, and the zero group is not read as a member that any value
            below one grounds
        """
        grounding = ["20 40 2 3", "Number of experts: 5", "Maximum error: 0.83"]

        assert find_ungrounded_numbers(answer, grounding) != []

    def test_the_flagged_token_is_reported_as_written(self):
        """
        GIVEN 5 000 in the answer and small numbers in the grounding
        WHEN the numbers are checked
        THEN the token comes back as written
        """
        grounding = ["20 40 2 3", "Number of experts: 5", "Maximum error: 0.83"]

        assert find_ungrounded_numbers("The panel had 5 000 experts", grounding) == ["5 000"]

    def test_a_list_of_groups_without_zeros_is_still_a_list(self):
        """
        GIVEN (100 200 300)
        WHEN the grounding states them separately
        THEN nothing is flagged
        """
        assert find_ungrounded_numbers("Values (100 200 300)", ["100, 200, 300"]) == []

    def test_a_zero_group_is_still_grounded_by_the_whole_number(self):
        """
        GIVEN 5 000
        WHEN the grounding states 5000
        THEN nothing is flagged
        """
        assert find_ungrounded_numbers("It is 5 000", ["5000"]) == []

    def test_a_zero_group_that_is_not_the_first_is_still_a_thousands_group(self):
        """
        GIVEN 2 500 000 and 10 050, whose zero-led group is not the first after the head
        WHEN the grounding holds their parts separately, and then the whole numbers
        THEN they are flagged, and then grounded
        """
        parts = ["2, 500, 0, 10, 50"]

        assert find_ungrounded_numbers("It is 2 500 000", parts) == ["2 500 000"]
        assert find_ungrounded_numbers("It is 10 050", parts) == ["10 050"]
        assert find_ungrounded_numbers("It is 2 500 000", ["2500000"]) == []
        assert find_ungrounded_numbers("It is 10 050", ["10050"]) == []

    def test_a_space_grouped_decimal_is_not_read_as_a_list(self):
        """
        GIVEN 1 000,5
        WHEN the grounding holds 1 and 0.5 separately, and then 1000.5
        THEN it is flagged, and then grounded
        """
        assert find_ungrounded_numbers("It is 1 000,5", ["1 and 0.5"]) == ["1 000,5"]
        assert find_ungrounded_numbers("It is 1 000,5", ["1000.5"]) == []

    def test_digits_around_a_dropped_citation_do_not_run_together(self):
        """
        GIVEN 5[1]000
        WHEN the grounding holds 5 and 0
        THEN nothing is flagged, because it is two numbers, not 5000
        """
        assert find_ungrounded_numbers("It is 5[1]000", ["5 and 0"]) == []
        assert find_ungrounded_numbers("It is 5[1]000", ["5 and 7"]) == ["000"]


class TestDotGroupedThousands:
    """Czech and German answers group thousands with dots and use a decimal comma."""

    def test_a_dotted_thousands_number_with_a_decimal_comma_is_one_number(self):
        """
        GIVEN 1.000,50
        WHEN the grounding holds 1000.50
        THEN nothing is flagged
        """
        assert find_ungrounded_numbers("It is 1.000,50", ["value 1000.50"]) == []

    def test_a_dotted_thousands_number_is_reported_when_only_its_parts_are_known(self):
        """
        GIVEN 1.000,50
        WHEN the grounding holds only 1 and 50
        THEN it is flagged as written
        """
        assert find_ungrounded_numbers("It is 1.000,50", ["1 and 50"]) == ["1.000,50"]

    def test_one_dot_group_reads_as_a_decimal_or_as_thousands(self):
        """
        GIVEN 1.234
        WHEN the grounding holds 1234, and then 1.234
        THEN it is grounded both times
        """
        assert find_ungrounded_numbers("It is 1.234", ["1234"]) == []
        assert find_ungrounded_numbers("It is 1.234", ["1.234"]) == []

    def test_one_dot_group_is_reported_when_neither_reading_holds(self):
        """
        GIVEN 7.250
        WHEN the grounding holds 7 and 250 separately
        THEN it is flagged
        """
        assert find_ungrounded_numbers("It is 7.250", ["7 and 250"]) == ["7.250"]

    def test_two_dot_groups_read_only_as_thousands(self):
        """
        GIVEN 12.345.678
        WHEN the grounding holds 12345678, and then only 12.345 and 678
        THEN it is grounded, and then flagged
        """
        assert find_ungrounded_numbers("It is 12.345.678", ["12345678"]) == []
        assert find_ungrounded_numbers("It is 12.345.678", ["12.345 and 678"]) == ["12.345.678"]

    def test_a_decimal_below_one_is_not_read_as_a_thousands_group(self):
        """
        GIVEN 0.250 and 0,250, which no thousands group can start with a zero
        WHEN the grounding holds 250, and then 0.25
        THEN they are flagged, and then grounded
        """
        assert find_ungrounded_numbers("It is 0.250", ["250"]) == ["0.250"]
        assert find_ungrounded_numbers("It is 0,250", ["250"]) == ["0,250"]
        assert find_ungrounded_numbers("It is 0.250", ["0.25"]) == []
        assert find_ungrounded_numbers("It is 0,250", ["0.25"]) == []

    def test_a_decimal_with_four_digits_after_the_dot_is_not_a_thousands_group(self):
        """
        GIVEN 1.2345
        WHEN the grounding holds 1.2345, and then 12345
        THEN it is grounded, and then flagged
        """
        assert find_ungrounded_numbers("It is 1.2345", ["1.2345"]) == []
        assert find_ungrounded_numbers("It is 1.2345", ["12345"]) == ["1.2345"]


class TestCommaGroupsWithZeros:
    """A comma group of three digits that starts with zero is a thousands group."""

    def test_a_zero_led_comma_group_is_never_a_list_member(self):
        """
        GIVEN 5,000,000
        WHEN the grounding holds 5 and 0.83
        THEN it is flagged, because 000 is not the 0 that 0.83 truncates to
        """
        assert find_ungrounded_numbers("It is 5,000,000", ["5", "0.83"]) == ["5,000,000"]

    def test_a_zero_led_comma_group_is_grounded_by_the_whole_number(self):
        """
        GIVEN 5,000,000
        WHEN the grounding holds 5000000
        THEN nothing is flagged
        """
        assert find_ungrounded_numbers("It is 5,000,000", ["5000000"]) == []

    def test_short_zero_members_of_a_list_are_still_members(self):
        """
        GIVEN 6,0,8
        WHEN the grounding holds 6, 0 and 8, and then only 6 and 8
        THEN it is grounded, and then flagged
        """
        assert find_ungrounded_numbers("It is 6,0,8", ["6 0 8"]) == []
        assert find_ungrounded_numbers("It is 6,0,8", ["6 8"]) == ["6,0,8"]

    def test_a_comma_before_three_digits_may_be_a_decimal_comma(self):
        """
        GIVEN 5,000
        WHEN the grounding holds 5, and then only 6
        THEN it is grounded, and then flagged
        """
        assert find_ungrounded_numbers("It is 5,000", ["5"]) == []
        assert find_ungrounded_numbers("It is 5,000", ["6"]) == ["5,000"]


class TestNarrowCompoundNames:
    """Only names that start with a capital lose their hyphenated number."""

    @pytest.mark.parametrize(
        ("answer", "reported"),
        [
            ("The error-15.3 was high", ["15.3"]),
            ("The peak-3 was high", ["3"]),
            ("The n-1 rule", ["1"]),
        ],
    )
    def test_a_lowercase_hyphenated_number_is_still_checked(self, answer: str, reported: list[str]):
        """
        GIVEN a lowercase word, a hyphen and a number
        WHEN the grounding lacks the number
        THEN the number is reported
        """
        assert find_ungrounded_numbers(answer, ["nothing"]) == reported

    def test_a_dropped_name_does_not_turn_a_following_hyphen_into_a_sign(self):
        """
        GIVEN GPT-4-5
        WHEN the grounding has nothing
        THEN -5 is not reported, and 5 is checked as a plain number
        """
        assert find_ungrounded_numbers("Use GPT-4-5 here", ["nothing"]) == ["5"]

    @pytest.mark.parametrize("answer", ["doc1-5", "[1]-5", "2026-09-29-5"])
    def test_a_dropped_token_of_another_kind_does_not_make_a_sign_either(self, answer: str):
        """
        GIVEN a mixed token, a citation and a date, each directly followed by -5
        WHEN the grounding has 5
        THEN nothing is flagged, because no minus became a sign
        """
        assert find_ungrounded_numbers(answer, ["5"]) == []

    def test_a_range_after_a_lowercase_word_is_a_range(self):
        """
        GIVEN x-20-40
        WHEN the grounding has 20 and 40
        THEN nothing is flagged
        """
        assert find_ungrounded_numbers("Set x-20-40 now", ["20 40"]) == []

    def test_a_week_range_does_not_report_a_negative(self):
        """
        GIVEN week-3-5
        WHEN the grounding has nothing
        THEN no negative number is reported
        """
        assert find_ungrounded_numbers("In week-3-5", ["nothing"]) == ["3", "5"]


class TestCitationLabelSet:
    """Only source words label a citation; any other word makes the bracket ordinary."""

    def test_a_bracket_with_quantity_words_is_not_a_citation(self):
        """
        GIVEN [lower 6, upper 11]
        WHEN the citations are checked with no sources
        THEN it passes, because the bracket is not a citation
        """
        assert check_citations("The range [lower 6, upper 11].", set()) is True

    def test_the_numbers_of_such_a_bracket_are_checked(self):
        """
        GIVEN [lower 6, upper 11]
        WHEN the grounding has 6 and 11, and then has neither
        THEN nothing is flagged, and then both are
        """
        answer = "The range [lower 6, upper 11]."

        assert find_ungrounded_numbers(answer, ["6 11"]) == []
        assert find_ungrounded_numbers(answer, ["nothing"]) == ["6", "11"]

    def test_a_range_of_quartile_names_is_not_a_citation(self):
        """
        GIVEN [Q1-Q3]
        WHEN the citations are checked with no sources
        THEN it passes
        """
        assert check_citations("Between [Q1-Q3].", set()) is True

    @pytest.mark.parametrize(
        ("form", "named"),
        [
            ("[Source 1, Source 2]", {1, 2}),
            ("[SOURCE 3]", {3}),
            ("[sources 1-2]", {1, 2}),
            ("[src 4]", {4}),
            ("[doc1]", {1}),
            ("[Docs 2]", {2}),
            ("[Document 5]", {5}),
            ("[Ref. 3]", {3}),
            ("[refs 2, 3]", {2, 3}),
            ("[Reference: 4]", {4}),
            ("[Excerpt 2]", {2}),
            ("[Passage #6]", {6}),
            ("[Zdroj 1]", {1}),
            ("[zdroje 1, 2]", {1, 2}),
            ("[Dokument 3]", {3}),
            ("[\u00daryvek 2]", {2}),
            ("[Pas\u00e1\u017e 4]", {4}),
            ("[\u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a 3]", {3}),
            ("[\u0418\u0441\u0442\u043e\u0447\u043d\u0438\u043a 3]", {3}),
        ],
    )
    def test_a_source_word_labels_a_citation(self, form: str, named: set[int]):
        """
        GIVEN a bracket labelled with a source word, in any case, in English, Czech or Russian
        WHEN the citations are checked against exactly the numbers it names, and against none
        THEN it passes, and then fails, and its digits are not scanned as numbers
        """
        answer = f"See {form} here."

        assert check_citations(answer, named) is True
        assert check_citations(answer, set()) is False
        assert find_ungrounded_numbers(answer, ["nothing"]) == []

    @pytest.mark.parametrize(
        ("form", "named"),
        [
            ("[Documents 1, 9]", {1, 9}),
            ("[References 1-3]", {1, 2, 3}),
            ("[Excerpts 2]", {2}),
            ("[Passages 4, 5]", {4, 5}),
            ("[Zdroje 1]", {1}),
            ("[Zdroj\u016f 2]", {2}),
            ("[Dokumenty 3]", {3}),
            ("[\u00daryvky 2]", {2}),
            ("[\u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a\u0438 2]", {2}),
            ("[\u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a\u043e\u0432 1]", {1}),
        ],
    )
    def test_a_plural_or_inflected_source_word_labels_a_citation(self, form: str, named: set[int]):
        """
        GIVEN a bracket labelled with a plural or inflected source word
        WHEN the citations are checked against exactly the numbers it names, and against none
        THEN it passes, and then fails
        """
        answer = f"See {form} here."

        assert check_citations(answer, named) is True
        assert check_citations(answer, set()) is False

    def test_a_plural_label_counts_every_number(self):
        """
        GIVEN [Documents 1, 9]
        WHEN only source 1 was given
        THEN the check fails
        """
        assert check_citations("see [Documents 1, 9]", {1}) is False

    @pytest.mark.parametrize(
        "form",
        [
            "[reflection 3]",
            "[docker 3]",
            "[documentation 3]",
            "[document-like 3]",
            "[sourcery 3]",
            "[lower 6, upper 11]",
        ],
    )
    def test_a_longer_unrelated_word_does_not_label_a_citation(self, form: str):
        """
        GIVEN a bracket whose word only begins like a source word
        WHEN the citations are checked with no sources
        THEN it passes, because the bracket is ordinary text, and its numbers are scanned
        """
        answer = f"See {form} here."

        assert check_citations(answer, set()) is True
        assert find_ungrounded_numbers(answer, ["nothing"]) != []
