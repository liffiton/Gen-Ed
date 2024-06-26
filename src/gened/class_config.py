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
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.wrappers.response import Response

from .auth import get_auth, instructor_required
from .contexts import ContextConfig, context_required, have_registered_context
from .db import get_db
from .openai import LLMDict, get_completion, get_models, with_llm
from .tz import date_is_past

bp = Blueprint('class_config', __name__, url_prefix="/instructor/config", template_folder='templates')


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


@bp.route("/context/<int:ctx_id>")
@instructor_required
@context_required
def context_form(ctx_class: type[ContextConfig], ctx_id: int) -> str | Response:
    db = get_db()
    auth = get_auth()

    context_row = db.execute("SELECT * FROM contexts WHERE id=?", [ctx_id]).fetchone()

    # verify the current user can edit this context
    class_id = auth['class_id']
    if context_row['class_id'] != class_id:
        return abort(403)

    context_config = ctx_class.from_row(context_row)

    return render_template(context_config.template, context=context_row, context_config=context_config)


@bp.route("/context/set/<int:ctx_id>", methods=["POST"])
@instructor_required
@context_required
def set_context(ctx_class: type[ContextConfig], ctx_id: int) -> Response:
    db = get_db()
    auth = get_auth()

    # verify the current user can edit this context
    class_id = auth['class_id']
    context = db.execute("SELECT * FROM contexts WHERE id=?", [ctx_id]).fetchone()
    if context['class_id'] != class_id:
        return abort(403)

    context_json = ctx_class.from_request_form(context['name'], request.form).to_json()

    db.execute("UPDATE contexts SET config=? WHERE id=?", [context_json, ctx_id])
    db.commit()

    flash(f"Configuration for context '{context['name']}' set!", "success")
    return redirect(url_for(".config_form"))
