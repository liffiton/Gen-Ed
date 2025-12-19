# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import logging.config
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

import pyrage
from dotenv import load_dotenv
from flask import Flask, render_template, request, send_from_directory
from flask.wrappers import Response
from werkzeug.middleware.proxy_fix import ProxyFix

from . import (
    admin,
    auth,
    class_config,
    classes,
    db,
    db_admin,
    demo,
    docs,
    experiments,  # noqa: F401 -- importing the module registers an admin component
    filters,
    instructor,
    llm,
    lti,
    migrate,
    models,
    oauth,
    profile,
    tz,
)
from .components import GenEdComponent
from .db import get_db


class MissingEnvVarError(Exception):
    def __init__(self, varname: str):
        super().__init__(f"Required environment variable not set: {varname}")


class InvalidAGEKeyError(Exception):
    def __init__(self, varname: str):
        super().__init__(f"Invalid key provided in {varname}.  Must be an Age public key or an SSH public key.")


class DBMissingModelError(Exception):
    def __init__(self, model_name: str):
        super().__init__(f"Configured model shortname not found in active models: {model_name}")


class GenEdAppBuilder:
    ''' A class to incrementally set up and finally build a complete Gen-Ed application. '''

    def __init__(self, import_name: str, app_config: dict[str, Any], instance_path: Path | None):
        '''
        Args:
            module_name: The name of the application's package (preferred) or module.
                        E.g., call this as GenEdAppBuilder(__name__, ...) from package/__init__.py.
            app_config: A dictionary containing application-specific configuration for the Flask object (w/ CAPITALIZED keys)
            instance_path: A path to the instance folder (for the database file, primarily)
        '''
        # load config values from .env file
        load_dotenv()

        # set up instance path from env variable if not provided
        if instance_path is None:
            try:
                instance_path = Path(os.environ["FLASK_INSTANCE_PATH"])
            except KeyError:
                print("Instance path not set and FLASK_INSTANCE_PATH environment variable not found.")
                sys.exit(1)
        # Flask() requires an absolute instance path
        instance_path = instance_path.resolve()
        # ensure instance_path folder exists
        instance_path.mkdir(parents=True, exist_ok=True)

        # create the base Flask application object
        self._app = Flask(import_name, instance_path=str(instance_path), instance_relative_config=True)
        # alias for simpler code below
        app = self._app

        testing = self._app.debug or app_config.get("TESTING", False)
        self._init_logging(testing=testing)

        # build the app's complete configuration
        self._config_app(app_config)

        # set up places to store app-specific data on the Flask instance
        app.extensions['gen_ed_config_tables'] = {}      # map: name(str) -> ConfigTable object

        # registry of installed components for this application, stored on the Flask instance
        # list[GenEdComponent]
        app.extensions['gen_ed_components'] = []

        # set up middleware to fix headers from a proxy if configured as such
        if os.environ.get("FLASK_APP_BEHIND_PROXY", "").lower() in ("yes", "true", "1"):
            app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)  # type: ignore[method-assign]

        #from werkzeug.middleware.profiler import ProfilerMiddleware
        #app.wsgi_app = ProfilerMiddleware(app.wsgi_app)

        # enable iframe LTI loads (SameSite=Lax will break those)
        @app.before_request
        def set_cookie_policy() -> None:
            if request.headers.get('Sec-Fetch-Dest') == 'iframe':
                app.config['SESSION_COOKIE_SAMESITE'] = 'None'
                # and SESSION_COOKIE_SECURE should still be set from base config
            else:
                # needs to be set/reset on every request, since app.config persists
                app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

        # strip whitespace before and after {% ... %} template statements
        app.jinja_env.lstrip_blocks = True
        app.jinja_env.trim_blocks = True

        # Inject auth data into template contexts
        @app.context_processor
        def inject_auth_data() -> dict[str, Any]:
            return { 'auth': auth.get_auth() }

        @app.route('/')
        def landing() -> str:
            return render_template("landing.html")

        @app.route('/.well-known/<path:path>')
        def well_known(path: Path) -> Response:
            return send_from_directory(Path(app.instance_path) / '.well-known', path)

    def _init_logging(self, *, testing: bool) -> None:
        """ Configure logging.
        (https://flask.palletsprojects.com/en/3.0.x/logging/#basic-configuration)
        Important to do this to make sure logging is configured before any
        logging is done, include via app.logger or when Waitress starts
        serving.  Both Flask and Waitress will create their own basic loggers
        if logging is not yet configured.  This can cause missing logs or
        double-logging.  If I configure logging first here, then Flask and
        Waitress will not set up logging themselves, and everything is good.
        """
        if not testing:
            logging.config.dictConfig({
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
                },
            })
        else:
            # For testing/debugging, ensure DEBUG level logging.
            logging.getLogger().setLevel(logging.DEBUG)
            logging.getLogger('markdown_it').setLevel(logging.INFO)  # avoid noisy debug logging in markdown_it
            #import logging_tree
            #logging_tree.printout()
            logging.debug("DEBUG logging enabled.")  # This appears to be required for the config to "stick"?

    def _config_app(self, app_config: dict[str, Any]) -> None:
        # alias to simplify code
        app = self._app

        # base config for all applications
        base_config = dict(
            # Some simple/weak XSS/CSRF protection
            SESSION_COOKIE_SECURE=True,
            SESSION_COOKIE_HTTPONLY=True,
            #SESSION_COOKIE_SAMESITE='Lax',  # will be set in before_request handler above
            # Cache timeout for static files (seconds)
            SEND_FILE_MAX_AGE_DEFAULT=3*60*60,  # 3 hours
            # Default redirect after login (may want to override with a tool endpoint)
            DEFAULT_LOGIN_ENDPOINT='landing',
            # Free query tokens given to new users
            DEFAULT_TOKENS=20,
            # Default data retention length (prune user data with no activity for this period of time)
            RETENTION_TIME_DAYS=2*365,  # 2 years

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
        #  - SYSTEM_API_KEY: the "system" LLM API key used in certain situations
        #  - SYSTEM_MODEL_SHORTNAME: shortname of model (in db) used for 'system' completions
        #  - DEFAULT_CLASS_MODEL_SHORTNAME: shortname of model (in db) used as default for new classes
        #    (see models table in db)
        for varname in ["SECRET_KEY", "SYSTEM_API_KEY", "SYSTEM_MODEL_SHORTNAME", "DEFAULT_CLASS_MODEL_SHORTNAME"]:
            try:
                env_var = os.environ[varname]
            except KeyError as e:
                raise MissingEnvVarError(varname) from e
            base_config[varname] = env_var

        # Optional variables:
        #  - AGE_PUBLIC_KEY: used to encrypt database backups and exports
        varname = "AGE_PUBLIC_KEY"
        try:
            env_var = os.environ[varname]
            # test the key
            if env_var.startswith('ssh'):
                pyrage.ssh.Recipient.from_str(env_var)
            else:
                pyrage.x25519.Recipient.from_str(env_var)
            base_config[varname] = env_var
        except pyrage.RecipientError as e:
            raise InvalidAGEKeyError(varname) from e
        except KeyError:
            app.logger.warning(f"{varname} environment variable not set.")

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

        # ensure applications have unique secret keys if testing multiple applications with same SECRET_KEY env var
        total_config['SECRET_KEY'] = str(total_config['APPLICATION_TITLE']) + str(total_config['SECRET_KEY'])

        # configure the application
        app.config.from_mapping(total_config)

    def add_component(self, component: GenEdComponent) -> None:
        # Register component identity/metadata
        components: list[GenEdComponent] = self._app.extensions['gen_ed_components']
        components.append(component)

        if component.navbar_item_template is not None:
            self._app.config['NAVBAR_ITEM_TEMPLATES'].append(component.navbar_item_template)
        if component.config_table is not None:
            ct = component.config_table
            ct_map = self._app.extensions['gen_ed_config_tables']
            assert ct.name not in ct_map  # don't allow registering the same name twice
            ct_map[ct.name] = ct  # will be used in class_config/config_table.py

    def _register_core_blueprints(self) -> None:
        app = self._app
        app.register_blueprint(admin.bp, url_prefix='/admin')
        app.register_blueprint(auth.bp, url_prefix='/auth')
        app.register_blueprint(classes.bp, url_prefix='/classes')
        app.register_blueprint(demo.bp, url_prefix='/demo')
        app.register_blueprint(instructor.bp, url_prefix='/instructor')
        app.register_blueprint(lti.bp, url_prefix='/lti')
        app.register_blueprint(oauth.bp, url_prefix='/oauth')
        app.register_blueprint(profile.bp, url_prefix='/profile')
        app.register_blueprint(models.bp, url_prefix="/models")
        class_config_bp = class_config.build_blueprint(app)  # requires building, using data stored in app.extensions['gen_ed_config_tables']
        app.register_blueprint(class_config_bp, url_prefix='/instructor/config')

    def _check_db(self) -> None:
        """ Check that the database contains necessary data. """
        app = self._app

        # Validate that the system and default class models exist and are active.
        try:
            for var in "SYSTEM_MODEL_SHORTNAME", "DEFAULT_CLASS_MODEL_SHORTNAME":
                shortname = app.config[var]
                model = llm.get_model(by_shortname=shortname)
                if not model or not model.active:
                    raise DBMissingModelError(shortname)
        except sqlite3.OperationalError:
            # e.g., pre-migration, no 'active' column; just warn
            app.logger.warning("Error looking up default active model.  You may need to run migrations.")


    def build(self) -> Flask:
        """ Finalize the app with all registered components and return a complete Flask app. """
        app = self._app
        components: list[GenEdComponent] = app.extensions['gen_ed_components']

        # register blueprints (core + any component blueprints)
        self._register_core_blueprints()
        for component in components:
            if bp := component.blueprint:
                app.register_blueprint(bp)

        # initialize core modules with other setup needs
        db.init_app(app)
        db_admin.init_app(app)
        docs.init_app(app, url_prefix='/docs')
        filters.init_app(app)
        migrate.init_app(app)
        oauth.init_app(app)
        tz.init_app(app)

        # run setup and checks that depend on the database (iff it is initialized)
        # must come after db.init_app(app) to ensure db is closed at end of context manager
        with app.app_context():
            db_conn = get_db()
            try:
                db_conn.execute("SELECT 1 FROM consumers LIMIT 1")
                db_conn.execute("SELECT 1 FROM models LIMIT 1")
                # check any registered component data sources
                for component in components:
                    if ds := component.data_source:
                        db_conn.execute(f"SELECT 1 FROM {ds.table_name}")
            except sqlite3.OperationalError:
                # database is not initialized, but we may be running initdb or a migration now, so that's okay
                pass
            else:
                # database has been initialized (no errors reading from those two tables)
                self._check_db()
                db_admin.rebuild_views()
                lti.reload_consumers()

        return app
