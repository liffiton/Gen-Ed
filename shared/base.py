from logging.config import dictConfig
import os
import sys


from dotenv import load_dotenv
from flask import render_template
import markupsafe

from shared import admin, auth, db, instructor, lti, tz


def configure_app_base(app):

    # Configure logging (from https://flask.palletsprojects.com/en/2.2.x/logging/#basic-configuration)
    # Important to do this to make sure logging is configured before Waitress
    # starts serving.  Waitress will create its own basic logger if logging is
    # not yet configured.  Flask will then lazy-load its *own* logger when I
    # first try to log something, causing double-logging.  If I configure
    # logging first here, then Waitress will not set up logging itself, and
    # everything is good.
    if not app.debug:
        dictConfig({
            'version': 1,
            'formatters': {'default': {
                'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
            }},
            'handlers': {'wsgi': {
                'class': 'logging.StreamHandler',
                'stream': 'ext://flask.logging.wsgi_errors_stream',
                'formatter': 'default'
            }},
            'root': {
                'level': 'INFO',
                'handlers': ['wsgi']
            }
        })

    #from werkzeug.middleware.profiler import ProfilerMiddleware
    #app.wsgi_app = ProfilerMiddleware(app.wsgi_app)

    # strip whitespace before and after {% ... %} template statements
    app.jinja_env.lstrip_blocks = True
    app.jinja_env.trim_blocks = True

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # load config values from .env file
    load_dotenv()
    try:
        openai_key = os.environ["OPENAI_API_KEY"]
    except KeyError:
        app.logger.error("OPENAI_API_KEY environment variable not set.")
        sys.exit(1)

    # base config for all applications
    app.config.from_mapping(
        OPENAI_API_KEY=openai_key,
        PYLTI_CONFIG={
            # will be loaded from the consumers table in the database
            "consumers": { }
        },
    )

    db.init_app(app)
    tz.init_app(app)

    app.register_blueprint(admin.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(instructor.bp)
    app.register_blueprint(lti.bp)

    # Inject auth data into template contexts
    @app.context_processor
    def inject_auth_data():
        return dict(auth=auth.get_session_auth())

    # Set up a Jinja filter for table cell contents
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

    @app.route('/')
    def index():
        return render_template("landing.html")
