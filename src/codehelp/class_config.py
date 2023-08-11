import json
from dataclasses import dataclass, asdict, field

from flask import Blueprint, current_app, flash, g, redirect, render_template, request, url_for

from plum.db import get_db
from plum.auth import get_auth, instructor_required
from plum.instructor import get_common_class_settings
from plum.openai import get_models


bp = Blueprint('class_config', __name__, url_prefix="/instructor/config", template_folder='templates')


def _default_langs():
    return current_app.config['DEFAULT_LANGUAGES']


@dataclass
class ClassConfig:
    languages: list[str] = field(default_factory=_default_langs)
    default_lang: str = None
    avoid: str = ''


def get_class_config():
    if 'class_config' not in g:
        auth = get_auth()
        class_id = auth['class_id']

        if class_id is None:
            g.class_config = ClassConfig()
        else:
            db = get_db()
            config_row = db.execute("SELECT config FROM classes WHERE id=?", [class_id]).fetchone()
            class_config_dict = json.loads(config_row['config'])
            g.class_config = ClassConfig(**class_config_dict)

    return g.class_config


@bp.route("/")
@instructor_required
def config_form():
    class_config = get_class_config()
    class_row, link_reg_state = get_common_class_settings()

    return render_template("instructor_config_form.html", class_row=class_row, link_reg_state=link_reg_state, class_config=class_config, models=get_models())


@bp.route("/set", methods=["POST"])
@instructor_required
def set_config():
    db = get_db()
    auth = get_auth()

    # only trust class_id from auth, not from user
    class_id = auth['class_id']

    class_config = ClassConfig(
        languages=request.form.getlist('languages[]'),
        default_lang=request.form.get('default_lang', None),
        avoid=request.form['avoid'],
    )
    class_config_json = json.dumps(asdict(class_config))

    db.execute("UPDATE classes SET config=? WHERE id=?", [class_config_json, class_id])
    db.commit()

    flash("Configuration set!", "success")
    return redirect(url_for(".config_form"))
