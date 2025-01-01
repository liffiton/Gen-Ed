# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from pathlib import Path
from typing import Any

from flask.app import Flask

from gened import base

from . import context_config, deletion_handler, helper, queries, tutor


def create_app(test_config: dict[str, Any] | None = None, instance_path: Path | None = None) -> Flask:
    ''' Flask app factory.  Create and configure the application. '''

    # App-specific configuration
    module_dir = Path(__file__).resolve().parent
    app_config = dict(
        APPLICATION_TITLE='CodeHelp',
        APPLICATION_AUTHOR='Mark Liffiton',
        FAVICON='icon.png',
        SUPPORT_EMAIL='support@codehelp.app',
        HELP_LINK_TEXT='Get Help',
        DATABASE_NAME='codehelp.db',  # will be combined with app.instance_path in gened.create_app_base()
        DOCS_DIR=module_dir / 'docs',
        # Data retention length (prune user data with no activity for this period of time)
        RETENTION_TIME_DAYS=2*365,  # 2 years
        DEFAULT_LANGUAGES=[
            "Conceptual Question",
            "C",
            "C++",
            "Java",
            "Javascript",
            "OCaml",
            "Python",
            "Rust",
        ],
    )

    # load test config if provided, potentially overriding above config
    if test_config is not None:
        app_config = app_config | test_config

    # register app-specific functionality with gened
    deletion_handler.register_with_gened()
    queries.register_with_gened()

    # create the base application
    app = base.create_app_base(__name__, app_config, instance_path)

    # register blueprints specific to this application variant
    app.register_blueprint(context_config.bp)
    app.register_blueprint(helper.bp)
    app.register_blueprint(tutor.bp)

    # register our custom context configuration with Gen-Ed
    # and grab a reference to the app's markdown filter
    context_config.register(app)

    # add navbar items
    app.config['NAVBAR_ITEM_TEMPLATES'].append("tutor_nav_item.html")

    return app
