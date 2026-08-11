# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import json
from typing import Any

from flask import Flask
from flask.json.provider import DefaultJSONProvider
from markupsafe import Markup, escape

from .markdown import render_markdown


def _make_titled_span(title: str, text: str, max_title_len: int = 500) -> Markup:
    if len(title) > max_title_len:
        title = title[:max_title_len] + " ..."
    title = title.replace('\n', Markup('&#13;'))
    title = title.replace('\'', Markup('&#39;'))
    return Markup("<span title='{}'>{}</span>").format(title, text)


def fmt_user(value: str) -> Markup:
    '''Format a user array (JSON) to be displayed in a table cell.'''
    if not value:
        return Markup()

    display_name, auth_provider, display_extra = json.loads(value)
    if display_extra:
        title_attr = Markup("title='{}'").format(display_extra)
    else:
        title_attr = Markup("")

    return Markup("{} <span class='is-size-7 has-text-grey' {}>({})</span>").format(display_name, title_attr, auth_provider)


def fmt_response_txt(value: str) -> Markup:
    '''Format response text to be displayed in a table cell.'''
    if not value:
        return Markup()

    text = json.loads(value)

    if isinstance(text, str):
        return _make_titled_span(escape(text), str(len(text)))

    else:
        # assume a dictionary
        html_string = Markup("\n<br>\n").join(
            _make_titled_span(escape(val), f"{key} ({len(val)})")
            for key, val in text.items() if val
        )
        return html_string


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
    app.jinja_env.filters['markdown'] = render_markdown
