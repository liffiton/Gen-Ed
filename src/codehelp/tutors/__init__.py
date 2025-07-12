from flask import Blueprint
from markupsafe import Markup

from gened.class_config import ConfigTable, register_config_table

from . import admin, data
from .chat import bp as chat_bp
from .guided import TutorConfig
from .guided import bp as guided_bp

bp = Blueprint('tutors', __name__, url_prefix='/tutor', template_folder='templates')
bp.register_blueprint(chat_bp)

admin.register_with_gened()

# Register the configuration UI inside gened's class_config module
guided_tutors_config_table = ConfigTable(
    config_item_class=TutorConfig,
    name='guided_tutor',
    db_table_name='tutors',
    display_name='focused tutor',
    display_name_plural='focused tutors',
    help_text=Markup('<p><i>Caution! Under development.</i></p>'),
    requires_experiment='chats_experiment',
    edit_form_template='guided_tutor_edit_form.html',
    routes=guided_bp,
)
register_config_table(guided_tutors_config_table)


def register_with_gened() -> None:
    data.register_with_gened()

__all__ = [
    "bp",
    "register_with_gened",
]
