# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from pathlib import Path

from flask.app import Flask

from gened.base import GenEdAppBuilder

from . import queries


def create_app(test_config: dict[str, str] | None = None, instance_path: Path | None = None) -> Flask:
    ''' Flask app factory.  Create and configure the application. '''

    # App-specific configuration
    module_dir = Path(__file__).resolve().parent
    app_config = dict(
        APPLICATION_TITLE='Language Tutor',
        APPLICATION_AUTHOR='Mark Liffiton',
        SUPPORT_EMAIL='mliffito@iwu.edu',
        DATABASE_NAME='language.db',
        DOCS_DIR=module_dir / 'docs',
    )

    # load test config if provided, potentially overriding above config
    if test_config is not None:
        app_config = app_config | test_config

    # create the base application
    builder = GenEdAppBuilder(__name__, app_config, instance_path)
    builder.add_component(queries.gened_component)
    app = builder.build()

    return app
