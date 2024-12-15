# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import json
import re
from typing import TypedDict

import markupsafe
from flask import Blueprint, current_app, redirect, render_template, request, url_for
from werkzeug.wrappers.response import Response

from gened.auth import class_enabled_required, get_auth, login_required
from gened.db import get_db
from gened.llm import LLM, with_llm
from gened.queries import get_history, get_query

from . import prompts

bp = Blueprint('helper', __name__, url_prefix="/check", template_folder='templates')


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



class ErrorSet(TypedDict):
    original: str
    error_types: list[str]

def insert_corrections_html(original: str, errors: list[ErrorSet]) -> str:
    # escape user inputs now, since we will be adding HTML soon
    jinja_escape = current_app.jinja_env.filters['e']
    original = jinja_escape(original)

    if not errors:
        return original

    error_mapping = {jinja_escape(item['original']): [jinja_escape(x) for x in item['error_types']] for item in errors}

    # Escape substrings to safely use them in regex
    escaped_substrings = [re.escape(sub) for sub in error_mapping]

    # Create a regex pattern to match any of the substrings
    pattern = r"(" + r"|".join(escaped_substrings) + r")"

    def replacement(match: re.Match[str]) -> str:
        matched_text = match.group(0)
        error_types = "".join(f'<li>{item}</li>' for item in error_mapping[matched_text])
        return f'<span class="writing_error" tabindex="0">{matched_text}<span class="is-size-6 writing_error_details">{error_types}</span></span>'

    # Replace matches with wrapped spans
    result = re.sub(pattern, replacement, original)
    return markupsafe.Markup(result)


@bp.route("/view/<int:query_id>")
@login_required
def help_view(query_id: int) -> str:
    query_row, responses = get_query(query_id)
    assert query_row
    assert responses
    history = get_history()

    if 'main' in responses:
        print(responses['main'])
        response_data = json.loads(responses['main'])
        marked_up = insert_corrections_html(query_row['writing'], response_data['errors'])
    else:
        marked_up = ""

    return render_template("help_view.html", query=query_row, marked_up=marked_up, responses=responses, history=history)


async def run_query_prompts(llm: LLM, writing: str) -> tuple[list[dict[str, str]], dict[str, str]]:
    ''' Run the given query through the LLM.

    Returns a tuple containing:
      1) A list of response objects from the OpenAI completion (to be stored in the database)
      2) A dictionary of response text, potentially including the key 'main'.
    '''
    task_main = asyncio.create_task(
        llm.get_completion(
            messages=prompts.make_main_prompt(writing),
            extra_args={'response_format': {'type': 'json_object'}},
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


def run_query(llm: LLM, writing: str) -> int:
    query_id = record_query(writing)

    responses, texts = asyncio.run(run_query_prompts(llm, writing))

    record_response(query_id, responses, texts)

    return query_id


def record_query(writing: str) -> int:
    db = get_db()
    auth = get_auth()
    role_id = auth.cur_class.role_id if auth.cur_class else None

    cur = db.execute(
        "INSERT INTO queries (writing, user_id, role_id) VALUES (?, ?, ?)",
        [writing, auth.user_id, role_id]
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
    writing = request.form["writing"]

    query_id = run_query(llm, writing)

    return redirect(url_for(".help_view", query_id=query_id))
