# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from pathlib import Path
from typing import Any

from flask import send_from_directory
from flask.app import Flask
from flask.wrappers import Response
from plum import base

from . import class_config, helper, tutor


def create_app(test_config: dict[str, Any] | None = None, instance_path: Path | None = None) -> Flask:
    ''' Flask app factory.  Create and configure the application. '''

    # App-specific configuration
    module_dir = Path(__file__).resolve().parent
    app_config = dict(
        APPLICATION_TITLE='CodeHelp',
        APPLICATION_AUTHOR='Mark Liffiton',
        SUPPORT_EMAIL='support@codehelp.app',
        HELP_LINK_TEXT='Get Help',
        DATABASE_NAME='codehelp.db',  # will be combined with app.instance_path in plum.create_app_base()
        DOCS_DIR=module_dir / 'docs',
        DEFAULT_LANGUAGES=[
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

    # create the base application
    app = base.create_app_base(__name__, app_config, instance_path)

    # register blueprints specific to this application variant
    app.register_blueprint(class_config.bp)
    app.register_blueprint(helper.bp)
    app.register_blueprint(tutor.bp)

    # make a simple route for the .well-known directory
    @app.route('/.well-known/<path:path>')
    def well_known(path: Path) -> Response:
        return send_from_directory('.well-known', path)

    # add navbar items
    app.config['NAVBAR_ITEM_TEMPLATES'].append("tutor_nav_item.html")

    return app
