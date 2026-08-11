# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import threading

import pytest
from markupsafe import Markup

from gened.markdown import render_markdown


def test_math_block() -> None:
    assert render_markdown("\\[x^2\\]\n") == Markup("\\[x^2\\]\n")


def test_math_folded_in_paragraph() -> None:
    assert render_markdown("Eq \\[x^2\\] in paragraph\n") == Markup("<p>Eq \\[x^2\\]\n in paragraph</p>\n")


def test_math_inline() -> None:
    assert render_markdown("\\(x^2\\) here\n") == Markup("<p>\\(x^2\\) here</p>\n")


def test_math_in_blockquote_closed() -> None:
    assert render_markdown("> \\[\n> x\n> \\]\n") == Markup("<blockquote>\n\\[\n&gt; x\n&gt; \\]\n</blockquote>\n")


def test_math_does_not_swallow_surrounding_text() -> None:
    # regression test: the front-end math_block rule (regex 'exec' with a
    # multiline '^') could match an equation on a later line and drop the text
    # before/between equations; the backend must preserve all of it
    text = str(render_markdown("Some intro text.\n\\[ a \\]\nMore text.\n\\[ b \\]\nFinal text.\n"))
    assert "Some intro text." in text
    assert "More text." in text
    assert "Final text." in text
    assert "\\[ a \\]" in text
    assert "\\[ b \\]" in text


def test_math_block_with_trailing_text() -> None:
    text = str(render_markdown("\\[x^2\\] trailing text\n"))
    assert "\\[x^2\\]" in text
    assert "trailing text" in text


def test_tikz_fence() -> None:
    out = str(render_markdown("```tikz\n\\begin{tikzpicture}\n\\draw (0,0);\n\\end{tikzpicture}\n```"))
    assert out.startswith('<script type="text/tikz">')
    assert "\\begin{document}" in out
    assert "\\end{document}" in out
    assert out.rstrip().endswith("</script>")

    # Handles spaces after end tag without breaking
    out_spaced = str(render_markdown("```tikz\n\\begin{tikzpicture}\n\\draw (0,0);\n\\end{tikzpicture} \n```"))
    assert out_spaced.rstrip().endswith("</script>")

    # Escapes </ to prevent script tag injection
    out_script = str(render_markdown("```tikz\n</script><script>alert(1)</script>\n```"))
    assert "</script>" not in out_script[:-10]
    assert r"<\/" in out_script


def _render_with_timeout(text: str, timeout: float = 5.0) -> str:
    result: list[str] = []

    def _run() -> None:
        result.append(str(render_markdown(text)))

    thread = threading.Thread(target=_run)
    thread.start()
    thread.join(timeout)
    assert not thread.is_alive(), f"markdown rendering hung on input: {text!r}"
    assert result, f"renderer produced no output for input: {text!r}"
    return result[0]


@pytest.mark.parametrize("text", [
    "> \\[\n> x\n\n\\]\n",
    "> > \\[\n> > x\n\n\\]\n",
])
def test_unclosed_math_in_blockquote_does_not_hang(text: str) -> None:
    # regression test: a \[...\] whose closing \] falls outside the blockquote's
    # scope previously made the block rule return True without advancing
    # state.line, causing an infinite loop (Python) / a thrown error (JS)
    output = _render_with_timeout(text)
    assert "<blockquote>" in output
    assert "\\[" not in output
    assert "\\]" not in output
