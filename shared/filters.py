import json
import markupsafe


def make_titled_span(title, text):
    title = title.replace('\n', markupsafe.Markup('&#13;'))
    title = title.replace('\'', markupsafe.Markup('&#39;'))
    return markupsafe.Markup(f"<span title='{title}'>{text}</span>")


def init_app(app):
    jinja_escape = app.jinja_env.filters['e']

    # a Jinja filter for table cell contents
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

    # a Jinja filter for formatting response text
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
