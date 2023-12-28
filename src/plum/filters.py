import json
from collections.abc import Callable, Generator
from sqlite3 import Row
from typing import Any

import markupsafe
import mdx_truly_sane_lists
from flask import url_for
from flask.app import Flask
from markdown import Markdown
from markdown import util as md_util
from markdown.extensions import fenced_code, meta, smarty


def make_titled_span(title: str, text: str) -> str:
    title = title.replace('\n', markupsafe.Markup('&#13;'))
    title = title.replace('\'', markupsafe.Markup('&#39;'))
    return markupsafe.Markup(f"<span title='{title}'>{text}</span>")


def init_app(app: Flask) -> None:
    jinja_escape = app.jinja_env.filters['e']

    # Jinja filter for table cell contents
    @app.template_filter('tbl_cell')
    def table_cell_filter(value: Any) -> str:
        '''Format a value to be displayed in a table cell.'''
        _maxlen = 30
        strval = str(value)

        if strval == "None":
            return ""
        elif len(strval) > _maxlen:
            strval = strval.strip().replace('\r', '')
            strval = jinja_escape(strval)
            strval_trunc = strval[:_maxlen] + " ..."
            return make_titled_span(strval, strval_trunc)
        else:
            return strval

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
    # monkey-patch markdown and fenced_code extension to not escape HTML in
    # `inline code` or ``` code blocks -- we're already escaping everything,
    # code or not, so...
    md_util.code_escape = lambda text: text
    fenced_code.FencedBlockPreprocessor._escape = lambda self, text: text  # type: ignore[attr-defined]
    # only configure/init these once, not every time the filter is called
    markdown_extensions = [
        fenced_code.makeExtension(),
        meta.makeExtension(),
        #sane_lists.makeExtension(),
        mdx_truly_sane_lists.makeExtension(),
        smarty.makeExtension(),
    ]
    markdown_processor = Markdown(output_format="html", extensions=markdown_extensions)
    # make available to request handlers, not just as a Jinja filter
    app.markdown_processor = markdown_processor  # type: ignore[attr-defined]

    @app.template_filter('markdown')
    def markdown_filter(value: str) -> str:
        '''Convert markdown to HTML (after escaping).'''
        escaped = jinja_escape(value)
        html = markdown_processor.reset().convert(escaped)
        return markupsafe.Markup(html)

    # Jinja filter for displaying users w/ dynamic info popups in datatables
    # Expects a database row that contains
    # 'auth_provider', 'email', and 'auth_name'.
    @app.template_filter('user_cell')
    def user_filter(user_row: Row) -> str:
        display_name = user_row['display_name']
        assert isinstance(display_name, str)

        auth_provider = dict(user_row).get('auth_provider')
        if auth_provider in ('demo', 'local', None):
            return display_name
        elif auth_provider in ('lti', 'google', 'microsoft'):
            extra_info = user_row['email']
        elif auth_provider == 'github':
            extra_info = f"@{user_row['auth_name']}"
        else:
            app.logger.error(f"Unhandled/unexpected auth provider: {auth_provider}.")
            extra_info = ""

        display_name = jinja_escape(display_name)
        html = f"{display_name} <span class='is-size-7 has-text-grey' title='{extra_info}'>({auth_provider})</span>"
        return markupsafe.Markup(html)

    # If I ever want to use it...  Testing (10x repeating render_template
    # on a large instructor view page) yielded no appreciable speedup
    # over existing tables.html macro.
    #
    # Usage would be:
    #  {% set builder = columns | row_builder(edit_handler) %}
    #  {% for row in data %}
    #    <tr>
    #      {% for cell_val in builder(row) %}
    #        <td>{{ cell_val }}</td>
    #      {% endfor %}
    #    </tr>
    #  {% endfor %}
    @app.template_filter('row_builder')
    def row_builder(columns: list[list[str]], edit_handler: str | None) -> Callable[[Row], Generator[str, None, None]]:
        jinja_filters = app.jinja_env.filters
        col_names = [x[1] for x in columns]

        def filter_for(col: str) -> Callable[[Any], str]:
            if 'time' in col:
                return lambda r: jinja_filters['localtime'](r[col])
            if col == 'display_name':
                return lambda r: jinja_filters['user_cell'](r)
            if col == 'response_text':
                return lambda r: jinja_filters['fmt_response_txt'](r[col])
            else:
                return lambda r: jinja_filters['tbl_cell'](r[col])

        filters = [filter_for(col) for col in col_names]

        if edit_handler:
            filters.append(lambda r: f"""
            <a class="button is-warning is-small p-2" href="{ url_for(edit_handler, id=r['id'])}">Edit</a>
            """)

        def doit(row: Row) -> Generator[str, None, None]:
            for filt in filters:
                yield filt(row)
        return doit
