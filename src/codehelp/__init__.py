from plum import base
from . import helper, tutor


def create_app(test_config=None, instance_path=None):
    ''' Flask app factory.  Create and configure the application. '''

    # App-specific configuration
    app_config = dict(
        APPLICATION_TITLE='CodeHelp',
        HELP_LINK_TEXT='Get Help',
        DATABASE_NAME='codehelp.db',  # will be combined with app.instance_path in plum.create_app_base()
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
        app_config = app_config | test_config

    # create the base application
    app = base.create_app_base(__name__, app_config, instance_path)

    # register blueprints specific to this application variant
    app.register_blueprint(helper.bp)
    app.register_blueprint(tutor.bp)

    return app
