# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import datetime as dt

from flask import (
    Blueprint,
    current_app,
    render_template,
)
from werkzeug.wrappers.response import Response

from .auth import get_auth, instructor_required
from .contexts import bp as contexts_bp
from .contexts import have_registered_context
from .db import get_db
from .openai import LLMDict, get_completion, get_models, with_llm
from .tz import date_is_past

bp = Blueprint('class_config', __name__, url_prefix="/instructor/config", template_folder='templates')

@bp.before_request
@instructor_required
def before_request() -> None:
    """ Apply decorator to protect all class_config blueprint endpoints. """

bp.register_blueprint(contexts_bp)


@bp.route("/")
@instructor_required
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

    contexts = None
    if have_registered_context():
        # get contexts
        contexts = db.execute("""
            SELECT contexts.*
            FROM contexts
            WHERE contexts.class_id=?
            ORDER BY contexts.class_order
        """, [class_id]).fetchall()
        contexts = [dict(c) for c in contexts]  # for conversion to json

    return render_template("instructor_class_config.html", class_row=class_row, link_reg_state=link_reg_state, models=get_models(), contexts=contexts)


@bp.route("/test_llm")
@instructor_required
@with_llm()
def test_llm(llm_dict: LLMDict) -> Response | dict[str, str | None]:
    response, response_txt = asyncio.run(get_completion(
        client=llm_dict['client'],
        model=llm_dict['model'],
        prompt="Please write 'OK'"
    ))

    if 'error' in response:
        return {'result': 'error', 'msg': 'Error!', 'error': f"<b>Error:</b><br>{response_txt}"}
    else:
        if response_txt != "OK":
            current_app.logger.error(f"LLM check had no error but responded not 'OK'?  Response: {response_txt}")
        return {'result': 'success', 'msg': 'Success!', 'error': None}
