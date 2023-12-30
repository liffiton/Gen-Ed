# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import os
import sqlite3
import sys
from logging.config import dictConfig
from pathlib import Path
from typing import Any

import flask.app
from dotenv import load_dotenv
from flask import Flask, render_template
from werkzeug.middleware.proxy_fix import ProxyFix

from . import (
    admin,
    auth,
    classes,
    db,
    demo,
    docs,
    filters,
    instructor,
    lti,
    migrate,
    oauth,
    profile,
    tz,
)


def create_app_base(import_name: str, app_config: dict[str, Any], instance_path: Path | None) -> flask.app.Flask:
    ''' Create a base Plum application.
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
            instance_path = Path(os.environ["FLASK_INSTANCE_PATH"])
        except KeyError:
            raise KeyError("FLASK_INSTANCE_PATH environment variable not set.") from None
    # ensure instance_path folder exists
    if not instance_path.is_dir():
        raise FileNotFoundError(f"FLASK_INSTANCE_PATH ({instance_path}) not found.")
    # Flask() requires an absolute instance path
    instance_path = instance_path.resolve()

    # create the Flask application object
    app = Flask(import_name, instance_path=str(instance_path), instance_relative_config=True)

    #from werkzeug.middleware.profiler import ProfilerMiddleware
    #app.wsgi_app = ProfilerMiddleware(app.wsgi_app)

    # strip whitespace before and after {% ... %} template statements
    app.jinja_env.lstrip_blocks = True
    app.jinja_env.trim_blocks = True

    # base config for all applications
    base_config = dict(
        # Some simple/weak XSS/CSRF protection
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        # Free query tokens given to new users
        DEFAULT_TOKENS=10,
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

    # Add vars set in .env, loaded by load_dotenv() above, to config dictionary.
    # Required variables:
    #  - SECRET_KEY: used by Flask to sign session cookies
    #  - OPENAI_API_KEY: the "system" API key used in certain situations
    for varname in ["SECRET_KEY", "OPENAI_API_KEY"]:
        try:
            env_var = os.environ[varname]
            base_config[varname] = env_var
        except KeyError:
            app.logger.error(f"{varname} environment variable not set.")
            sys.exit(1)
    # CLIENT_ID/CLIENT_SECRET vars are used by authlib:
    #   https://docs.authlib.org/en/latest/client/flask.html#configuration
    # But the application will run without them; it just won't provide login
    # options for any providers where the keys are missing.
    for provider in ["GOOGLE", "MICROSOFT", "GITHUB"]:
        try:
            client_id_key = f"{provider}_CLIENT_ID"
            client_secret_key = f"{provider}_CLIENT_SECRET"
            base_config[client_id_key] = os.environ[client_id_key]
            base_config[client_secret_key] = os.environ[client_secret_key]
        except KeyError:
            # Just warn, but continue
            app.logger.warning(f"{provider}_CLIENT_ID and/or {provider}_CLIENT_SECRET environment variables not set.  SSO from {provider} will not be enabled.")

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

    # set up middleware to fix headers from a proxy if configured as such
    if os.environ.get("FLASK_APP_BEHIND_PROXY", "").lower() in ("yes", "true", "1"):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)  # type: ignore[method-assign]

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
    migrate.init_app(app)
    oauth.init_app(app)
    tz.init_app(app)

    app.register_blueprint(admin.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(demo.bp)
    app.register_blueprint(instructor.bp)
    app.register_blueprint(lti.bp)
    app.register_blueprint(oauth.bp)
    app.register_blueprint(profile.bp)
    app.register_blueprint(classes.bp)

    # Only register the docs blueprint if we're configured with a documentation directory
    docs_dir = app.config.get('DOCS_DIR')
    if docs_dir:
        app.register_blueprint(docs.bp)

    # Inject auth data into template contexts
    @app.context_processor
    def inject_auth_data() -> dict[str, Any]:
        return { 'auth': auth.get_auth() }

    @app.route('/')
    def landing() -> str:
        return render_template("landing.html")

    return app
