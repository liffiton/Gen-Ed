import os

from flask import Flask
from codehelp.helper import helper


def create_app():
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='thisisaverysupersecretkeyjustthebestest',
        # DATABASE=os.path.join(app.instance_path, 'codehelp.db'),
    )

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    app.register_blueprint(helper)

    return app
