import os

from flask import Flask

from shared import base
from shared import admin
from . import helper


def create_app(test_config=None):
    # create and configure the app

    app = Flask(__name__, instance_relative_config=True)

    base.configure_app_base(app)

    app.config.from_mapping(
        APPLICATION_TITLE='CodeHelp',
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

    # load consumers from DB (but only if we're not in testing mode)
    if not app.config['TESTING']:
        with app.app_context():
            admin.reload_consumers()

    # register blueprints specific to this application variant
    app.register_blueprint(helper.bp)

    return app
