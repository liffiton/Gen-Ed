import os

from flask import Flask

from shared import base
from . import helper


def create_app(test_config=None):
    # create and configure the app

    app = Flask(__name__, instance_relative_config=True)

    app.config.from_mapping(
        APPLICATION_TITLE='CodeHelp',
        HELP_LINK_TEXT='Get Help',
        DATABASE=os.path.join(app.instance_path, 'codehelp.db'),
        SECRET_KEY='_oeofMFVOeT-Z730Ksz44Q',
        LANGUAGES=[
            "c",
            "c++",
            "java",
            "javascript",
            "ocaml",
            "python",
            "rust",
        ],
    )

    # load test config if provided, potentially overriding above config
    if test_config is not None:
        app.config.from_mapping(test_config)

    base.configure_app_base(app)

    # register blueprints specific to this application variant
    app.register_blueprint(helper.bp)

    return app
