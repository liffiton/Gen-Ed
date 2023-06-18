import json
from markdown import Markdown, util as md_util
from markdown.extensions import fenced_code, sane_lists, smarty
import markupsafe


def make_titled_span(title, text):
    title = title.replace('\n', markupsafe.Markup('&#13;'))
    title = title.replace('\'', markupsafe.Markup('&#39;'))
    return markupsafe.Markup(f"<span title='{title}'>{text}</span>")


def init_app(app):
    jinja_escape = app.jinja_env.filters['e']

    # Jinja filter for table cell contents
    @app.template_filter('tbl_cell')
    def table_cell_filter(value):
        '''Format a value to be displayed in a table cell.'''
        value = str(value)

        if value == "None":
            return ""
        elif len(value) > 30:
            value = value.strip().replace('\r', '')
            value = jinja_escape(value)
            value_trunc = value[:30] + " ..."
            return make_titled_span(value, value_trunc)
        else:
            return value

    # Jinja filter for formatting response text
    @app.template_filter('fmt_response_txt')
    def fmt_response_txt(value):
        '''Format response text to be displayed in a table cell.'''
        text = json.loads(value)

        if isinstance(text, str):
            return make_titled_span(jinja_escape(text), len(text))

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
    md_util.code_escape = lambda x: x
    fenced_code.FencedBlockPreprocessor._escape = lambda self, x: x
    # only configure/init these once, not every time the filter is called
    markdown_extensions = [
        fenced_code.makeExtension(),
        sane_lists.makeExtension(),
        smarty.makeExtension()
    ]
    markdown_processor = Markdown(output_format="html5", extensions=markdown_extensions)

    @app.template_filter('markdown')
    def markdown_filter(value):
        '''Convert markdown to HTML (after escaping).'''
        escaped = jinja_escape(value)
        html = markdown_processor.reset().convert(escaped)
        return markupsafe.Markup(html)

    # Jinja filter for displaying users w/ dynamic info popups in datatables
    # Expects a *tuple* of (display_name, row_object) where row_object contains
    # 'auth_provider', 'email', and 'auth_name'.
    @app.template_filter('user_cell')
    def user_filter(user_tuple):
        display_name, user_row = user_tuple

        auth_provider = dict(user_row).get('auth_provider')
        if auth_provider in ('demo', 'local', None):
            return display_name
        elif auth_provider == 'lti':
            extra_info = user_row['email']
        elif auth_provider == 'google':
            extra_info = user_row['email']
        elif auth_provider == 'github':
            extra_info = f"@{user_row['auth_name']}"
        else:
            app.logger.error(f"Unhandled/unexpected auth provider: {auth_provider}.")
            extra_info = ""

        display_name = jinja_escape(display_name)
        html = f"{display_name} <span class='is-size-7 has-text-grey' title='{extra_info}'>({auth_provider})</span>"
        return markupsafe.Markup(html)
