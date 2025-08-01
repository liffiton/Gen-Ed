# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from pathlib import Path
from typing import Any

from flask.app import Flask

from gened.base import GenEdAppBuilder

from . import contexts, deletion_handler, queries, tutors


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
    )

    # load test config if provided, potentially overriding above config
    if test_config is not None:
        app_config = app_config | test_config

    # register app-specific functionality with gened
    deletion_handler.register_with_gened()

    # create the base application
    builder = GenEdAppBuilder(__name__, app_config, instance_path)
    builder.add_component(contexts.gened_component)
    builder.add_component(queries.gened_component)
    builder.add_component(tutors.gened_component)
    app = builder.build()

    return app
