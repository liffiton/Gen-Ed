from logging.config import dictConfig
import os
import sqlite3
import sys

from dotenv import load_dotenv
from flask import Flask, render_template

from . import admin, auth, db, demo, instructor, filters, lti, tz


def create_app_base(import_name, app_config, instance_path):
    ''' Create a base PLuM application.
    Args:
        module_name: The name of the application's package (preferred) or module.
                     E.g., call this as plum.create_app_base(__name__, ...) from package/__init__.py.
        app_config: A dictionary containing application-specific configuration for the Flask object (w/ CAPITALIZED keys)
        instance_path: A path to the instance folder (for the database file, primarily)

    Returns:
        A configured Flask application object.
    '''
    # load config values from .env file
    load_dotenv()

    # set up instance path from env variable if not provided
    if instance_path is None:
        try:
            instance_path = os.environ["FLASK_INSTANCE_PATH"]
        except KeyError:
            raise Exception("FLASK_INSTANCE_PATH environment variable not set.")
    # ensure instance_path folder exists
    if not os.path.isdir(instance_path):
        raise FileNotFoundError(f"FLASK_INSTANCE_PATH ({instance_path}) not found.")
    # Flask() requires an absolute instance path
    instance_path = os.path.abspath(instance_path)

    # create the Flask application object
    app = Flask(import_name, instance_path=instance_path, instance_relative_config=True)

    #from werkzeug.middleware.profiler import ProfilerMiddleware
    #app.wsgi_app = ProfilerMiddleware(app.wsgi_app)

    # strip whitespace before and after {% ... %} template statements
    app.jinja_env.lstrip_blocks = True
    app.jinja_env.trim_blocks = True

    # OPENAI_API_KEY set in .env, loaded by load_dotenv() above.
    try:
        openai_key = os.environ["OPENAI_API_KEY"]
    except KeyError:
        app.logger.error("OPENAI_API_KEY environment variable not set.")
        sys.exit(1)

    # base config for all applications
    base_config = dict(
        DEFAULT_TOKENS=10,
        OPENAI_API_KEY=openai_key,
        PYLTI_CONFIG={
            # will be loaded from the consumers table in the database
            "consumers": { }
        },
        # finalize the database path now that we have an instance_path
        # may be overridden by app_config (e.g. if test_config sets DATABASE)
        DATABASE=os.path.join(app.instance_path, app_config['DATABASE_NAME']),
        # list of navbar item templates; will be extended by specific create_app()s
        NAVBAR_ITEM_TEMPLATES=[],
    )

    # build total configuration
    total_config = base_config | app_config

    # configure the application
    app.config.from_mapping(total_config)

    # Configure logging (from https://flask.palletsprojects.com/en/2.2.x/logging/#basic-configuration)
    # Important to do this to make sure logging is configured before Waitress
    # starts serving.  Waitress will create its own basic logger if logging is
    # not yet configured.  Flask will then lazy-load its *own* logger when I
    # first try to log something, causing double-logging.  If I configure
    # logging first here, then Waitress will not set up logging itself, and
    # everything is good.
    if not app.debug and not app.testing:
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
    else:
        # For testing/debugging, ensure DEBUG level logging.
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
        #import logging_tree
        #logging_tree.printout()
        logging.debug("DEBUG logging enabled.")  # This appears to be required for the config to "stick"?

    # load consumers from DB (but only if the database is initialized)
    try:
        with app.app_context():
            admin.reload_consumers()
    except sqlite3.OperationalError:
        # the table doesn't exist yet -- that's fine
        pass

    admin.init_app(app)
    db.init_app(app)
    filters.init_app(app)
    tz.init_app(app)

    app.register_blueprint(admin.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(demo.bp)
    app.register_blueprint(instructor.bp)
    app.register_blueprint(lti.bp)

    # Inject auth data into template contexts
    @app.context_processor
    def inject_auth_data():
        return dict(auth=auth.get_session_auth())

    @app.route('/')
    def landing():
        return render_template("landing.html")

    return app
