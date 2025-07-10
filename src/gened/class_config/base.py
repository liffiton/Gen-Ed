# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import datetime as dt

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    render_template,
    request,
)
from werkzeug.wrappers.response import Response

from gened.auth import get_auth_class, instructor_required
from gened.db import get_db
from gened.llm import LLM, get_models, with_llm
from gened.redir import safe_redirect
from gened.tz import date_is_past

from .config_table import bp as config_table_bp
from .extra_sections import get_extra_sections_data

bp = Blueprint('class_config', __name__, template_folder='templates')

bp.register_blueprint(config_table_bp)

@bp.before_request
@instructor_required
def before_request() -> None:
    """ Apply decorator to protect all class_config blueprint endpoints. """


@bp.route("/")
def config_form() -> str:
    db = get_db()

    cur_class = get_auth_class()
    class_id = cur_class.class_id

    class_row = db.execute("""
        SELECT classes.id, classes.enabled, classes_user.link_ident, classes_user.link_reg_expires, classes_user.link_anon_login, classes_user.llm_api_key, classes_user.model_id
        FROM classes
        LEFT JOIN classes_user
          ON classes.id = classes_user.class_id
        WHERE classes.id=?
    """, [class_id]).fetchone()

    # TODO: refactor into function for checking start/end dates
    expiration_date = class_row['link_reg_expires']
    if expiration_date is None:
        link_reg_state = None  # not a user-created class
    elif date_is_past(expiration_date):
        link_reg_state = "disabled"
    elif expiration_date == dt.date.max:
        link_reg_state = "enabled"
    else:
        link_reg_state = "date"

    extra_sections_data = get_extra_sections_data()
    print(extra_sections_data)

    models = get_models(plus_id=class_row['model_id'])

    return render_template("instructor_class_config.html", class_row=class_row, link_reg_state=link_reg_state, user_is_creator=cur_class.user_is_creator, models=models, extra_sections_data=extra_sections_data)


@bp.route("/save/access", methods=["POST"])
def save_access_config() -> Response:
    db = get_db()

    # only trust class_id from auth, not from user
    cur_class = get_auth_class()
    class_id = cur_class.class_id

    if 'is_user_class' in request.form:
        # only present for user classes, not LTI
        link_reg_active = request.form['link_reg_active']
        if link_reg_active == "disabled":
            new_date = str(dt.date.min)
        elif link_reg_active == "enabled":
            new_date = str(dt.date.max)
        else:
            new_date = request.form['link_reg_expires']

        class_link_anon_login = 1 if 'class_link_anon_login' in request.form else 0
        db.execute("UPDATE classes_user SET link_reg_expires=?, link_anon_login=? WHERE class_id=?", [new_date, class_link_anon_login, class_id])

    class_enabled = 1 if 'class_enabled' in request.form else 0
    db.execute("UPDATE classes SET enabled=? WHERE id=?", [class_enabled, class_id])
    db.commit()
    flash("Class access configuration updated.", "success")

    return safe_redirect(request.referrer, default_endpoint="profile.main")

@bp.route("/save/llm", methods=["POST"])
def save_llm_config() -> Response:
    db = get_db()

    # only trust class_id from auth, not from user
    cur_class = get_auth_class()
    class_id = cur_class.class_id

    # only class creators can edit LLM config
    if not cur_class.user_is_creator:
        abort(403)

    if 'clear_llm_api_key' in request.form:
        db.execute("UPDATE classes_user SET llm_api_key='' WHERE class_id=?", [class_id])
        db.commit()
        flash("Class API key cleared.", "success")

    elif 'save_llm_form' in request.form:
        if 'llm_api_key' in request.form:
            db.execute("UPDATE classes_user SET llm_api_key=? WHERE class_id=?", [request.form['llm_api_key'], class_id])
        db.execute("UPDATE classes_user SET model_id=? WHERE class_id=?", [request.form['model_id'], class_id])
        db.commit()
        flash("Class language model configuration updated.", "success")

    return safe_redirect(request.referrer, default_endpoint="profile.main")


@bp.route("/test_llm")
@with_llm()
def test_llm(llm: LLM) -> str:
    response, response_txt = asyncio.run(llm.get_completion(prompt="Please write 'OK'"))

    if 'error' in response:
        return f"<b>Error:</b><br>{response_txt}"
    else:
        if response_txt != "OK":
            current_app.logger.error(f"LLM check had no error but responded not 'OK'?  Response: {response_txt}")
        return "ok"
