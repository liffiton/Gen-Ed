# SPDX-FileCopyrightText: 2026 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import re
from collections.abc import Callable, Sequence
from typing import cast

from markdown_it import MarkdownIt
from markdown_it.common.utils import escapeHtml
from markdown_it.renderer import RendererHTML, RendererProtocol
from markdown_it.rules_block import StateBlock
from markdown_it.rules_inline import StateInline
from markdown_it.token import Token
from markdown_it.utils import EnvType, OptionsDict
from markupsafe import Markup

_MATH_BLOCK_RE = re.compile(r"^\\\[(.+?)\\\]", re.DOTALL)
_INLINE_MATH_RE = re.compile(r"^\\\((.+?)\\\)", re.DOTALL)


def _make_inline_math_rule(token_name: str, regex: re.Pattern[str]) -> Callable[[StateInline, bool], bool]:
    '''Create an inline rule matching `regex` and emitting a `token_name` math token.

    `regex` must be anchored at `^` and capture the math contents in group 1.
    '''
    def _rule(state: StateInline, silent: bool) -> bool:  # noqa: FBT001 - required by the markdown-it rule API
        match = regex.match(state.src[state.pos:])
        if not match:
            return False
        if not silent:
            token = state.push(token_name, "math", 0)
            token.content = match.group(1)
        state.pos += match.end()
        return True

    return _rule


def _math_block(state: StateBlock, beg_line: int, end_line: int, silent: bool) -> bool:  # noqa: FBT001 - required by the markdown-it rule API
    r'''Block rule matching a \[...\] equation that starts on its own line.

    Only reached at the start of a block; a \[...\] equation folded into a
    paragraph is handled by the inline `math_block` rule instead.
    '''
    begin = state.bMarks[beg_line] + state.tShift[beg_line]
    match = _MATH_BLOCK_RE.match(state.src[begin:])
    if not match:
        return False

    # only accept the match if the closing \] falls within this block's lines;
    # otherwise fall through so the inline rule can handle it inside a paragraph
    # (and state.line always advances when we return True)
    endpos = begin + match.end() - 1
    line = beg_line
    while line < end_line and endpos > state.eMarks[line]:
        line += 1
    if line >= end_line:
        return False

    # ensure no trailing non-whitespace on the line containing \];
    # otherwise let the inline rule handle it inside a paragraph
    if state.src[endpos + 1 : state.eMarks[line]].strip():
        return False

    if not silent:
        token = state.push("math_block", "math", 0)
        token.block = True
        token.content = match.group(1)
    state.line = line + 1
    return True


def _render_math_inline(
    _self: RendererProtocol,
    tokens: Sequence[Token],
    idx: int,
    _options: OptionsDict,
    _env: EnvType,
) -> str:
    return f"\\({escapeHtml(tokens[idx].content)}\\)"


def _render_math_block(
    _self: RendererProtocol,
    tokens: Sequence[Token],
    idx: int,
    _options: OptionsDict,
    _env: EnvType,
) -> str:
    # a math_block token also comes from an equation folded into a paragraph, where the trailing newline is harmless
    return f"\\[{escapeHtml(tokens[idx].content)}\\]\n"


def create_markdown_processor() -> MarkdownIt:
    r'''Create the app's Markdown renderer.

    Configured to preserve \( and \[ without rendering markdown within so we can
    render TeX math in the browser.
    '''
    markdown_processor = MarkdownIt("js-default")  # js-default: https://markdown-it-py.readthedocs.io/en/latest/security.html
    markdown_processor.disable("lheading")  # no "===" headings; can get confused by = on a line by itself

    renderer = cast("RendererHTML", markdown_processor.renderer)
    default_fence: Callable[[Sequence[Token], int, OptionsDict, EnvType], str] = renderer.rules["fence"]

    def _render_fence(
        _self: RendererProtocol,
        tokens: Sequence[Token],
        idx: int,
        options: OptionsDict,
        env: EnvType,
    ) -> str:
        token = tokens[idx]
        if token.info.strip() == "tikz":
            content = token.content
            if r"\begin{document}" not in content:
                content = r"\begin{document}" + content
            if r"\end{document}" not in content:
                content = content + r"\end{document}"
            content = content.replace("</", r"<\/")
            return f'<script type="text/tikz">{content}</script>\n'
        return default_fence(tokens, idx, options, env)

    markdown_processor.block.ruler.before("fence", "math_block", _math_block)
    markdown_processor.inline.ruler.before("escape", "math_block", _make_inline_math_rule("math_block", _MATH_BLOCK_RE))
    markdown_processor.inline.ruler.before("escape", "math_inline", _make_inline_math_rule("math_inline", _INLINE_MATH_RE))
    markdown_processor.add_render_rule("math_block", _render_math_block)
    markdown_processor.add_render_rule("math_inline", _render_math_inline)
    markdown_processor.add_render_rule("fence", _render_fence)

    return markdown_processor


_markdown_processor = create_markdown_processor()


def render_markdown(value: str) -> Markup:
    '''Convert markdown to HTML.'''
    # relying on MarkdownIt's escaping (w/o HTML parsing, due to "js-default"), so mark this as safe
    return Markup(_markdown_processor.render(value))  # noqa: S704 (unsafe use of Markup -- but we know we've escaped the input already)
