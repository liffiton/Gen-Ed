# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import json

from flask import Blueprint, redirect, render_template, request, url_for
from gened.auth import class_enabled_required, get_auth, login_required
from gened.db import get_db
from gened.openai import LLMConfig, get_completion, with_llm
from gened.queries import get_history, get_query
from werkzeug.wrappers.response import Response

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
        query_row, _ = get_query(query_id)   # _ because we don't need responses here

    history = get_history()

    return render_template("help_form.html", query=query_row, history=history)


@bp.route("/view/<int:query_id>")
@login_required
def help_view(query_id: int) -> str:
    query_row, responses = get_query(query_id)
    history = get_history()

    return render_template("help_view.html", query=query_row, responses=responses, history=history)


async def run_query_prompts(llm: LLMConfig, assignment: str, topics: str) -> tuple[list[dict[str, str]], dict[str, str]]:
    ''' Run the given query against the coding help system of prompts.

    Returns a tuple containing:
      1) A list of response objects from the OpenAI completion (to be stored in the database)
      2) A dictionary of response text, potentially including the key 'main'.
    '''
    task_main = asyncio.create_task(
        get_completion(
            client=llm.client,
            model=llm.model,
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


def run_query(llm: LLMConfig, assignment: str, topics: str) -> int:
    query_id = record_query(assignment, topics)

    responses, texts = asyncio.run(run_query_prompts(llm, assignment, topics))

    record_response(query_id, responses, texts)

    return query_id


def record_query(assignment: str, topics: str) -> int:
    db = get_db()
    auth = get_auth()
    role_id = auth['role_id']

    cur = db.execute(
        "INSERT INTO queries (assignment, topics, user_id, role_id) VALUES (?, ?, ?, ?)",
        [assignment, topics, auth['user_id'], role_id]
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
def help_request(llm: LLMConfig) -> Response:
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
    db.execute("UPDATE queries SET helpful=? WHERE id=? AND user_id=?", [value, query_id, auth['user_id']])
    db.commit()
    return ""
