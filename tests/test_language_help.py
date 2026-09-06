# SPDX-FileCopyrightText: 2026 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for the language_help component's HTML rendering helper."""

from markupsafe import Markup

from components.language_help.helper import ErrorSet, insert_corrections_html

ERROR_SPAN_OPEN = '<span class="writing_error" tabindex="0">'
ERROR_DETAILS_OPEN = '<span class="is-size-6 writing_error_details">'
ITEM = '<span class="item">'


def test_no_errors_simple() -> None:
    result = insert_corrections_html("Hello world.", [])
    assert str(result) == "<p>Hello world.</p>"


def test_no_errors_paragraphs() -> None:
    original = "Para one.\n\nPara two.\n\n\nPara three."
    result = insert_corrections_html(original, [])
    assert str(result) == "<p>Para one.</p><p>Para two.</p><p>Para three.</p>"


def test_no_errors_whitespace_normalized() -> None:
    original = "  Leading  and\ttabs.   \nSingle newline."
    result = insert_corrections_html(original, [])
    assert str(result) == "<p> Leading and tabs. Single newline.</p>"


def test_no_errors_empty() -> None:
    assert str(insert_corrections_html("", [])) == "<p></p>"
    assert str(insert_corrections_html("\n\n", [])) == "<p></p><p></p>"


def test_no_errors_html_escaped() -> None:
    original = '<script>alert("x")</script> & \'quotes\''
    result = insert_corrections_html(original, [])
    assert str(result) == "<p>&lt;script&gt;alert(&#34;x&#34;)&lt;/script&gt; &amp; &#39;quotes&#39;</p>"


def test_returns_markup() -> None:
    result = insert_corrections_html("Hello world.", [])
    assert isinstance(result, Markup)


def test_error_wrapped_in_span() -> None:
    original = "The cat sat on the mat."
    errors: list[ErrorSet] = [{'original': 'cat sat on the mat', 'error_types': ['capitalization']}]
    result = insert_corrections_html(original, errors)
    expected = (
        "<p>The "
        + ERROR_SPAN_OPEN + "cat sat on the mat" + ERROR_DETAILS_OPEN
        + ITEM + "- capitalization</span>"
        + "</span></span>"
        + ".</p>"
    )
    assert str(result) == expected


def test_error_types_html_escaped() -> None:
    original = "The cat sat."
    errors: list[ErrorSet] = [{'original': 'The cat', 'error_types': ['<b>bold</b> & more']}]
    result = insert_corrections_html(original, errors)
    assert ITEM + "- &lt;b&gt;bold&lt;/b&gt; &amp; more</span>" in str(result)
    assert "<b>bold</b>" not in str(result)


def test_error_fragment_html_escaped() -> None:
    original = "The <script>bad</script> thing happened."
    errors: list[ErrorSet] = [{'original': 'The <script>bad</script> thing', 'error_types': ['html']}]
    result = insert_corrections_html(original, errors)
    assert ERROR_SPAN_OPEN + "The &lt;script&gt;bad&lt;/script&gt; thing" in str(result)


def test_error_multi_line_fragment() -> None:
    original = "This is a very\nlong sentence here.\n\nNext para."
    errors: list[ErrorSet] = [{'original': 'a very long sentence', 'error_types': ['phrasing']}]
    result = insert_corrections_html(original, errors)
    assert ERROR_SPAN_OPEN + "a very long sentence" in str(result)
    assert str(result).count("<p>") == 2


def test_error_no_match() -> None:
    original = "Nothing to see here."
    errors: list[ErrorSet] = [{'original': 'not present', 'error_types': ['x']}]
    result = insert_corrections_html(original, errors)
    assert str(result) == "<p>Nothing to see here.</p>"


def test_error_across_paragraphs_not_matched() -> None:
    original = "first\n\nsecond"
    errors: list[ErrorSet] = [{'original': 'first second', 'error_types': ['x']}]
    result = insert_corrections_html(original, errors)
    assert str(result) == "<p>first</p><p>second</p>"


def test_error_multiple() -> None:
    original = "One error here and one error there."
    errors: list[ErrorSet] = [
        {'original': 'One error', 'error_types': ['grammar']},
        {'original': 'one error there', 'error_types': ['spelling']},
    ]
    result = insert_corrections_html(original, errors)
    s = str(result)
    assert s.count(ERROR_SPAN_OPEN) == 2
    assert ITEM + "- grammar</span>" in s
    assert ITEM + "- spelling</span>" in s


def test_error_blank_fragments_dropped() -> None:
    original = "The cat sat on the mat."
    errors: list[ErrorSet] = [
        {'original': '', 'error_types': ['blank']},
        {'original': ' \t\n  ', 'error_types': ['whitespace']},
        {'original': 'cat sat', 'error_types': ['real']},
    ]
    result = insert_corrections_html(original, errors)
    s = str(result)
    assert s.count(ERROR_SPAN_OPEN) == 1
    assert ITEM + "- real</span>" in s
    assert "blank" not in s
    assert "whitespace" not in s


def test_error_all_fragments_blank() -> None:
    original = "The cat sat.\n\nOn the mat."
    errors: list[ErrorSet] = [
        {'original': '', 'error_types': ['x']},
        {'original': '   ', 'error_types': ['y']},
    ]
    result = insert_corrections_html(original, errors)
    assert str(result) == "<p>The cat sat.</p><p>On the mat.</p>"


def test_error_overlapping_fragments_longest_first() -> None:
    original = "aaaa aaaa"
    errors: list[ErrorSet] = [
        {'original': 'aaaa aaaa', 'error_types': ['whole']},
        {'original': 'aaaa', 'error_types': ['part']},
    ]
    result = insert_corrections_html(original, errors)
    s = str(result)
    assert s.count(ERROR_SPAN_OPEN) == 1
    assert ITEM + "- whole</span>" in s
