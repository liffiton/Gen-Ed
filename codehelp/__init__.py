import os
import sys

from dotenv import load_dotenv
from flask import Flask, render_template

from . import auth
from . import db
from . import helper
from . import lti


def create_app():
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)

    load_dotenv()
    try:
        openai_key = os.environ["OPENAI_API_KEY"]
    except KeyError:
        print("Error:  OPENAI_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    app.config.from_mapping(
        SECRET_KEY='thisisaverysupersecretkeyjustthebestest',
        OPENAI_API_KEY=openai_key,
        PYLTI_CONFIG={
            # TODO: load this from / store this in the database for each registered consumer?
            "consumers": {
                "courses.iwu.edu": {
                    "secret": "MyMoodleoodleTest"
                }
            }
        },
        DATABASE=os.path.join(app.instance_path, 'codehelp.db'),
    )

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    db.init_app(app)

    app.register_blueprint(auth.bp)
    app.register_blueprint(helper.bp)
    app.register_blueprint(lti.bp)

    @app.route('/')
    def index():
        return render_template("index.html")

    return app
