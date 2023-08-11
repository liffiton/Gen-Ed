from pathlib import Path

from flask import send_from_directory

from plum import base
from . import class_config, helper, tutor


def create_app(test_config=None, instance_path=None):
    ''' Flask app factory.  Create and configure the application. '''

    # App-specific configuration
    module_dir = Path(__file__).resolve().parent
    app_config = dict(
        APPLICATION_TITLE='CodeHelp',
        HELP_LINK_TEXT='Get Help',
        DATABASE_NAME='codehelp.db',  # will be combined with app.instance_path in plum.create_app_base()
        DOCS_DIR=module_dir / 'docs',
        SECRET_KEY='_oeofMFVOeT-Z730Ksz44Q',
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
    def well_known(path):
        return send_from_directory('.well-known', path)

    # add navbar items
    app.config['NAVBAR_ITEM_TEMPLATES'].append("tutor_nav_item.html")

    return app
