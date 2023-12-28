from flask import Blueprint, render_template
from plum.auth import instructor_required
from plum.instructor import get_common_class_settings
from plum.openai import get_models

bp = Blueprint('class_config', __name__, url_prefix="/instructor/config", template_folder='templates')


@bp.route("/")
@instructor_required
def config_form() -> str:
    class_row, link_reg_state = get_common_class_settings()

    return render_template("instructor_config_form.html", class_row=class_row, link_reg_state=link_reg_state, models=get_models())
