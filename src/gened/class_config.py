# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import datetime as dt
from collections.abc import Callable

from flask import (
    Blueprint,
    current_app,
    render_template,
)

from .auth import get_auth, instructor_required
from .db import get_db
from .openai import LLMConfig, get_completion, get_models, with_llm
from .tz import date_is_past

bp = Blueprint('class_config', __name__, url_prefix="/instructor/config", template_folder='templates')

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
    auth = get_auth()

    class_id = auth['class_id']

    class_row = db.execute("""
        SELECT classes.id, classes.enabled, classes_user.link_ident, classes_user.link_reg_expires, classes_user.openai_key, classes_user.model_id
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


@bp.route("/test_llm")
@with_llm()
def test_llm(llm: LLMConfig) -> str:
    response, response_txt = asyncio.run(get_completion(
        client=llm.client,
        model=llm.model,
        prompt="Please write 'OK'"
    ))

    if 'error' in response:
        return f"<b>Error:</b><br>{response_txt}"
    else:
        if response_txt != "OK":
            current_app.logger.error(f"LLM check had no error but responded not 'OK'?  Response: {response_txt}")
        return "ok"
