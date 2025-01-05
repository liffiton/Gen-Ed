# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import json
from contextlib import suppress

from flask import (
    Blueprint,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.wrappers.response import Response

from gened.app_data import DataAccessError, get_query, get_user_data
from gened.auth import class_enabled_required, get_auth, login_required
from gened.db import get_db
from gened.llm import LLM, with_llm

from . import prompts

bp = Blueprint('helper', __name__, url_prefix="/ideas", template_folder='templates')


@bp.route("/")
@bp.route("/<int:query_id>")
@login_required
@class_enabled_required
def help_form(query_id: int | None = None) -> str:
    query_row = None

    # populate with a query+response if one is specified
    if query_id is not None:
        with suppress(DataAccessError):
            query_row = get_query(query_id)

    history = get_user_data(kind='queries', limit=10)

    return render_template("help_form.html", query=query_row, history=history)


@bp.route("/view/<int:query_id>")
@login_required
def help_view(query_id: int) -> Response | str:
    try:
        query_row = get_query(query_id)
    except DataAccessError:
        flash("Invalid id.", "warning")
        return make_response(render_template("error.html"), 400)

    if query_row['response']:
        responses = json.loads(query_row['response'])
    else:
        responses = {'error': "*No response -- an error occurred.  Please try again.*"}

    history = get_user_data(kind='queries', limit=10)

    return render_template("help_view.html", query=query_row, responses=responses, history=history)


async def run_query_prompts(llm: LLM, assignment: str, topics: str) -> tuple[list[dict[str, str]], dict[str, str]]:
    ''' Run the given query against the coding help system of prompts.

    Returns a tuple containing:
      1) A list of response objects from the OpenAI completion (to be stored in the database)
      2) A dictionary of response text, potentially including the key 'main'.
    '''
    task_main = asyncio.create_task(
        llm.get_completion(
            prompt=prompts.make_main_prompt(assignment, topics),
        )
    )

    # Store all responses received
    responses = []

    # And let's get the main response.
    response_main, response_txt = await task_main
    responses.append(response_main)

    if 'error' in response_main:
        return responses, {'error': response_txt}

    return responses, {'main': response_txt}


def run_query(llm: LLM, assignment: str, topics: str) -> int:
    query_id = record_query(assignment, topics)

    responses, texts = asyncio.run(run_query_prompts(llm, assignment, topics))

    record_response(query_id, responses, texts)

    return query_id


def record_query(assignment: str, topics: str) -> int:
    db = get_db()
    auth = get_auth()
    role_id = auth.cur_class.role_id if auth.cur_class else None

    cur = db.execute(
        "INSERT INTO queries (assignment, topics, user_id, role_id) VALUES (?, ?, ?, ?)",
        [assignment, topics, auth.user_id, role_id]
    )
    new_row_id = cur.lastrowid
    db.commit()

    assert new_row_id is not None
    return new_row_id


def record_response(query_id: int, responses: list[dict[str, str]], texts: dict[str, str]) -> None:
    db = get_db()

    db.execute(
        "UPDATE queries SET response_json=?, response_text=? WHERE id=?",
        [json.dumps(responses), json.dumps(texts), query_id]
    )
    db.commit()


@bp.route("/request", methods=["POST"])
@login_required
@class_enabled_required
@with_llm(use_system_key=True)
def help_request(llm: LLM) -> Response:
    assignment = request.form["assignment"]
    topics = request.form["topics"]

    query_id = run_query(llm, assignment, topics)

    return redirect(url_for(".help_view", query_id=query_id))


@bp.route("/post_helpful", methods=["POST"])
@login_required
def post_helpful() -> str:
    db = get_db()
    auth = get_auth()

    query_id = int(request.form['id'])
    value = int(request.form['value'])
    db.execute("UPDATE queries SET helpful=? WHERE id=? AND user_id=?", [value, query_id, auth.user_id])
    db.commit()
    return ""
