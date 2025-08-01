from flask import Blueprint
from markupsafe import Markup

from gened.base import GenEdComponent
from gened.class_config import ConfigShareLink, ConfigTable, register_config_table

from . import admin
from .chat import bp as chat_bp
from .data import TutorsDeletionHandler, chats_data_source
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
    share_links=[
        ConfigShareLink(
            'Focused tutor chat',
            'tutors.chat.new_chat_form',
            {'class_id', 'tutor_name'},
            requires_experiment='chats_experiment',
        ),
    ]
)
register_config_table(guided_tutors_config_table, guided_bp)


gened_component = GenEdComponent(
    blueprint=bp,
    navbar_item_template="tutor_nav_item.html",
    data_source=chats_data_source,
    deletion_handler=TutorsDeletionHandler,
)


__all__ = [
    "gened_component",
]
