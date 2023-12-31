import datetime as dt
import json
from dataclasses import Field, asdict
from sqlite3 import Row
from typing import Any, ClassVar, TypeVar

from flask import (
    Blueprint,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)
from typing_extensions import Protocol, Self
from werkzeug.datastructures import ImmutableMultiDict
from werkzeug.wrappers.response import Response

from .auth import get_auth, instructor_required
from .db import get_db
from .openai import get_models
from .tz import date_is_past

bp = Blueprint('class_config', __name__, url_prefix="/instructor/config", template_folder='templates')


class IsClassConfig(Protocol):
    # So it looks like a dataclass:
    __dataclass_fields__: ClassVar[dict[str, Field[Any]]]
    # So it can be generated from a request form:
    @classmethod
    def from_request_form(cls, form: ImmutableMultiDict[str, str]) -> Self:
        pass

_class_config_class: type[IsClassConfig] | None = None

def register_class_config(cls: type[IsClassConfig]) -> None:
    global _class_config_class  # noqa: PLW0603 (global statement)
    _class_config_class = cls


def get_common_class_settings() -> tuple[Row, str | None]:
    db = get_db()
    auth = get_auth()

    class_id = auth['class_id']

    class_row = db.execute("""
        SELECT classes.id, classes.enabled, classes_user.link_ident, classes_user.link_reg_expires, classes_user.openai_key, classes_user.model_id
        FROM classes
        LEFT JOIN classes_user
          ON classes.id = classes_user.class_id
        WHERE classes.id=?
    """, [class_id]).fetchone()

    expiration_date = class_row['link_reg_expires']
    if expiration_date is None:
        link_reg_state = None  # not a user-created class
    elif date_is_past(expiration_date):
        link_reg_state = "disabled"
    elif expiration_date == dt.date.max:
        link_reg_state = "enabled"
    else:
        link_reg_state = "date"

    return class_row, link_reg_state


T = TypeVar('T', bound='IsClassConfig')

def get_class_config(config_class: type[T]) -> T:
    if 'class_config' not in g:
        auth = get_auth()
        class_id = auth['class_id']

        if class_id is None:
            g.class_config = config_class()
        else:
            db = get_db()
            config_row = db.execute("SELECT config FROM classes WHERE id=?", [class_id]).fetchone()
            class_config_dict = json.loads(config_row['config'])
            g.class_config = config_class(**class_config_dict)

    return g.class_config


@bp.route("/")
@instructor_required
def config_form() -> str:
    class_config = get_class_config(_class_config_class) if _class_config_class is not None else None

    class_row, link_reg_state = get_common_class_settings()

    return render_template("instructor_class_config.html", class_row=class_row, link_reg_state=link_reg_state, class_config=class_config, models=get_models())


@bp.route("/set", methods=["POST"])
@instructor_required
def set_config() -> Response:
    if _class_config_class is None:
        return abort(404)

    db = get_db()
    auth = get_auth()

    # only trust class_id from auth, not from user
    class_id = auth['class_id']

    class_config = _class_config_class.from_request_form(request.form)
    class_config_json = json.dumps(asdict(class_config))

    db.execute("UPDATE classes SET config=? WHERE id=?", [class_config_json, class_id])
    db.commit()

    flash("Configuration set!", "success")
    return redirect(url_for(".config_form"))
