import os

from flask import Flask

from shared import base
from . import helper


def create_app(test_config=None):
    # create and configure the app

    app = Flask(__name__, instance_relative_config=True)

    app.config.from_mapping(
        APPLICATION_TITLE='Starburst',
        HELP_LINK_TEXT='Get Ideas',
        DATABASE=os.path.join(app.instance_path, 'starburst.db'),
        SECRET_KEY='qAg_CIdh0RqvpF1nvC79ng',
    )

    # load test config if provided, potentially overriding above config
    if test_config is not None:
        app.config.from_mapping(test_config)

    base.configure_app_base(app)

    # register blueprints specific to this application variant
    app.register_blueprint(helper.bp)

    return app
