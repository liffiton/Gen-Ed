from pathlib import Path

from plum import base
from . import class_config, helper


def create_app(test_config=None, instance_path=None):
    ''' Flask app factory.  Create and configure the application. '''

    # App-specific configuration
    module_dir = Path(__file__).resolve().parent
    app_config = dict(
        APPLICATION_TITLE='Starburst',
        HELP_LINK_TEXT='Generate Ideas',
        DATABASE_NAME='starburst.db',
        DOCS_DIR=module_dir / 'docs',
    )

    # load test config if provided, potentially overriding above config
    if test_config is not None:
        app_config = app_config | test_config

    # create the base application
    app = base.create_app_base(__name__, app_config, instance_path)

    # register blueprints specific to this application variant
    app.register_blueprint(class_config.bp)
    app.register_blueprint(helper.bp)

    return app
