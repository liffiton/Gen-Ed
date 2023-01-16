import os
import sys

from dotenv import load_dotenv
from flask import Flask

from . import helper


def create_app():
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)

    try:
        load_dotenv()
        openai_key = os.environ["OPENAI_API_KEY"]
    except KeyError:
        print("Error:  OPENAI_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    app.config.from_mapping(
        SECRET_KEY='thisisaverysupersecretkeyjustthebestest',
        OPENAI_API_KEY=openai_key,
        # DATABASE=os.path.join(app.instance_path, 'codehelp.db'),
    )

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    app.register_blueprint(helper.bp)

    return app
