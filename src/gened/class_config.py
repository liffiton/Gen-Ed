# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import datetime as dt
from collections.abc import Callable

from flask import (
    Blueprint,
    current_app,
    flash,
    render_template,
    request,
)
from werkzeug.wrappers.response import Response

from .auth import get_auth_class, instructor_required
from .db import get_db
from .llm import LLM, get_models, with_llm
from .redir import safe_redirect
from .tz import date_is_past

bp = Blueprint('class_config', __name__, template_folder='templates')

@bp.before_request
@instructor_required
def before_request() -> None:
    """ Apply decorator to protect all class_config blueprint endpoints. """


# Applications can also register additional forms/UI for including in the class
# configuration page.  Each must be provided as a function that renders *only*
# its portion of the configuration screen's UI.  The application is responsible
# for registering a blueprint with request handlers for any routes needed by
# that UI.
# This module global stores the render functions.
_extra_config_renderfuncs: list[Callable[[], str]] = []

def register_extra_section(render_func: Callable[[], str]) -> None:
    """ Register a new section for the class configuration UI.  (See above.)"""
    _extra_config_renderfuncs.append(render_func)


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

    extra_sections = [render() for render in _extra_config_renderfuncs]  # rendered HTML for any extra config sections

    return render_template("instructor_class_config.html", class_row=class_row, link_reg_state=link_reg_state, models=get_models(), extra_sections=extra_sections)


@bp.route("/save", methods=["POST"])
def save_config() -> Response:
    db = get_db()

    # only trust class_id from auth, not from user
    cur_class = get_auth_class()
    class_id = cur_class.class_id

    if 'clear_llm_api_key' in request.form:
        db.execute("UPDATE classes_user SET llm_api_key='' WHERE class_id=?", [class_id])
        db.commit()
        flash("Class API key cleared.", "success")

    elif 'save_access_form' in request.form:
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
