# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import json

import markupsafe
from flask.app import Flask
from markdown_it import MarkdownIt


def make_titled_span(title: str, text: str, max_title_len: int = 500) -> str:
    if len(title) > max_title_len:
        title = title[:max_title_len] + " ..."
    title = title.replace('\n', markupsafe.Markup('&#13;'))
    title = title.replace('\'', markupsafe.Markup('&#39;'))
    return markupsafe.Markup(f"<span title='{title}'>{text}</span>")


def init_app(app: Flask) -> None:
    jinja_escape = app.jinja_env.filters['e']

    # Jinja filter for formatting response text
    @app.template_filter('fmt_response_txt')
    def fmt_response_txt(value: str) -> str:
        '''Format response text to be displayed in a table cell.'''
        if not value:
            return ""

        text = json.loads(value)

        if isinstance(text, str):
            return make_titled_span(jinja_escape(text), str(len(text)))

        else:
            # assume a dictionary
            html_string = "\n<br>\n".join(
                make_titled_span(jinja_escape(val), f"{key} ({len(val)})")
                for key, val in text.items() if val
            )
            return markupsafe.Markup(html_string)

    # Jinja filter for converting Markdown to HTML
    markdown_processor = MarkdownIt("js-default")  # js-default: https://markdown-it-py.readthedocs.io/en/latest/security.html
    markdown_processor.inline.ruler.disable(['escape'])  # disable escaping so that \(, \[, etc. come through for TeX math

    @app.template_filter('markdown')
    def markdown_filter(value: str) -> str:
        '''Convert markdown to HTML.'''
        html = markdown_processor.render(value)
        # relying on MarkdownIt's escaping (w/o HTML parsing, due to "js-default"), so mark this as safe
        return markupsafe.Markup(html)
