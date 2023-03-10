import markupsafe


def init_app(app):
    @app.template_filter('tbl_cell')
    def table_cell_filter(value):
        '''Format a value to be displayed in a table cell.'''
        value = str(value)

        if len(value) > 30:
            value = value.strip().replace('\r', '')
            value = app.jinja_env.filters['e'](value)
            value_trunc = value[:30] + " ..."
            value_title = value.replace('\n', markupsafe.Markup('&#13;'))
            return markupsafe.Markup(f"<span title='{value_title}'>{value_trunc}</span>")
        else:
            return value
