# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import json
from typing import Any

from flask import Flask
from flask.json.provider import DefaultJSONProvider
from markdown_it import MarkdownIt
from markupsafe import Markup, escape


def make_titled_span(title: str, text: str, max_title_len: int = 500) -> str:
    if len(title) > max_title_len:
        title = title[:max_title_len] + " ..."
    title = title.replace('\n', Markup('&#13;'))
    title = title.replace('\'', Markup('&#39;'))
    return Markup(f"<span title='{title}'>{text}</span>")


def fmt_user(value: str) -> str:
    '''Format a user array (JSON) to be displayed in a table cell.'''
    if not value:
        return ""

    display_name, auth_provider, display_extra = json.loads(value)

    if display_extra:
        return Markup(f"{display_name} <span class='is-size-7 has-text-grey' title='{display_extra}'>({auth_provider})</span>")
    else:
        return Markup(f"{display_name} <span class='is-size-7 has-text-grey'>({auth_provider})</span>")


def fmt_response_txt(value: str) -> str:
    '''Format response text to be displayed in a table cell.'''
    if not value:
        return ""

    text = json.loads(value)

    if isinstance(text, str):
        return make_titled_span(escape(text), str(len(text)))

    else:
        # assume a dictionary
        html_string = "\n<br>\n".join(
            make_titled_span(escape(val), f"{key} ({len(val)})")
            for key, val in text.items() if val
        )
        return Markup(html_string)


def init_app(app: Flask) -> None:
    # Jinja filter for formatting certain fields
    app.jinja_env.filters['fmt_response_txt'] = fmt_response_txt
    app.jinja_env.filters['fmt_user'] = fmt_user

    # Customize app's JSON provider
    assert isinstance(app.json, DefaultJSONProvider)
    old_default = app.json.default
    def default(o: Any) -> Any:
        try:
            return old_default(o)
        except TypeError:
            # Allow functions through JSON serialization.
            # (Note that this does not properly serialize them, of course.)
            if callable(o):
                return '[function]'

            raise
    # monkey-patch app's current JSON provider
    app.json.default = default

    # Jinja filter for converting Markdown to HTML
    markdown_processor = MarkdownIt("js-default")  # js-default: https://markdown-it-py.readthedocs.io/en/latest/security.html
    markdown_processor.inline.ruler.disable(['escape'])  # disable escaping so that \(, \[, etc. come through for TeX math

    @app.template_filter('markdown')
    def markdown_filter(value: str) -> str:
        '''Convert markdown to HTML.'''
        html = markdown_processor.render(value)
        # relying on MarkdownIt's escaping (w/o HTML parsing, due to "js-default"), so mark this as safe
        return Markup(html)
