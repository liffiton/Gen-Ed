# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import json
import re
from collections.abc import Iterable
from contextlib import suppress
from typing import TypedDict

from flask import (
    Blueprint,
    abort,
    current_app,
    redirect,
    render_template,
    request,
    url_for,
)
from markupsafe import Markup
from werkzeug.wrappers.response import Response

from gened.access import class_enabled_required, login_required
from gened.app_data import DataAccessError
from gened.auth import get_auth
from gened.db import get_db
from gened.llm import LLM, with_llm

from . import prompts
from .data import queries_data_source

bp = Blueprint('language_helper', __name__, url_prefix="/check", template_folder='templates')


@bp.route("/")
@bp.route("/<int:query_id>")
@login_required
@class_enabled_required
def help_form(query_id: int | None = None) -> str:
    query_row = None

    # populate with a query+response if one is specified
    if query_id is not None:
        with suppress(DataAccessError):
            query_row = queries_data_source.get_row(query_id)

    history = queries_data_source.get_user_data(limit=10)

    return render_template("language_help_form.html", query=query_row, history=history)


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text)

class ErrorSet(TypedDict):
    original: str
    error_types: list[str]


_error_span = Markup(
    '<span class="writing_error" tabindex="0">{text}'
    '<span class="is-size-6 writing_error_details">{error_types}</span></span>'
)
_error_item = Markup('<span class="item">- {}</span>')


def insert_corrections_html(original: str, errors: list[ErrorSet]) -> Markup:
    # Escape user content at final assembly: Markup's .format()/.join() escape
    # plain-string arguments exactly once, so we can work with raw text until then.

    # blank lines become paragraph breaks; normalize all remaining whitespace
    # so we can be sure to match correctly
    paragraphs = [normalize_whitespace(p) for p in re.split(r"\n\n+", original)]

    # must normalize these the same way, since we're matching into normalized text;
    # drop blank fragments, which would match at every position
    error_mapping = {
        normalized: item['error_types']
        for item in errors
        if (normalized := normalize_whitespace(item['original'])).strip()
    }

    if not error_mapping:
        return _paragraphs_html(paragraphs)

    pattern = _error_pattern(error_mapping)

    return _paragraphs_html(_wrap_paragraph(p, pattern, error_mapping) for p in paragraphs)


def _paragraphs_html(paragraphs: Iterable[str | Markup]) -> Markup:
    # .join() escapes raw paragraphs and keeps Markup as-is; + keeps Markup as-is
    return Markup("<p>") + Markup("</p><p>").join(paragraphs) + Markup("</p>")


def _error_pattern(error_mapping: dict[str, list[str]]) -> re.Pattern[str]:
    # regex-escape substrings to safely use them in regex
    escaped_substrings = [re.escape(sub) for sub in error_mapping]

    # and match whitespace against *any* whitespace in the original
    # (un-normalized, and the LLM may have reformatted it)
    # note: replacing any escaped space with *literal* "\s+" string (to be used in pattern)
    # and: see this for explanation of weird replacement string: https://stackoverflow.com/questions/58328587/
    escaped_substrings = [re.sub(r"\\ ", r"\\s+", sub) for sub in escaped_substrings]

    # ensure matches don't start or end in the middle of a word
    # 2025-08-03: disabled -- helps with things like using lowercase 'i'
    # instead of 'I', but breaks matching in Chinese, for example...
    #escaped_substrings = [re.sub(r"^\b", r"\\b", sub) for sub in escaped_substrings]
    #escaped_substrings = [re.sub(r"\b$", r"\\b", sub) for sub in escaped_substrings]

    # create a regex pattern to match any of the substrings
    return re.compile(r"(" + r"|".join(escaped_substrings) + r")")


def _wrap_paragraph(paragraph: str, pattern: re.Pattern[str], error_mapping: dict[str, list[str]]) -> Markup:
    parts: list[str | Markup] = []
    last = 0
    for match in pattern.finditer(paragraph):
        parts.append(paragraph[last:match.start()])
        error_types = Markup("").join(_error_item.format(item) for item in error_mapping[match.group(0)])
        parts.append(_error_span.format(text=match.group(0), error_types=error_types))
        last = match.end()
    parts.append(paragraph[last:])
    return Markup("").join(parts)


@bp.route("/view/<int:query_id>")
@login_required
def help_view(query_id: int) -> Response | str:
    try:
        query_row = queries_data_source.get_row(query_id)
    except DataAccessError:
        abort(400, "Invalid id.")

    try:
        if query_row['response']:
            responses = json.loads(query_row['response'])
        else:
            responses = {'error': "*No response -- an error occurred.  Please try again.*"}
    except json.JSONDecodeError:
        current_app.logger.error(f"Failed to decode response for query {query_id}. Response: {query_row['response']}")
        responses = {'error': "*Error: The stored response is corrupt.*"}

    marked_up: str | Markup = ""
    if 'main' in responses:
        try:
            response_data = json.loads(responses['main'])
            marked_up = insert_corrections_html(query_row['writing'], response_data.get('errors'))
        except json.JSONDecodeError:
            current_app.logger.error(f"Invalid JSON in language_help response {query_id}: {responses['main']}")
            marked_up = Markup("<p class='has-text-danger'>*Error: The AI response could not be parsed.*</p>")

    history = queries_data_source.get_user_data(limit=10)

    return render_template("language_help_view.html", query=query_row, marked_up=marked_up, responses=responses, history=history)


async def run_query_prompts(llm: LLM, writing: str) -> tuple[list[dict[str, str]], dict[str, str]]:
    ''' Run the given query through the LLM.

    Returns a tuple containing:
      1) A list of response objects from the LLM completion (to be stored in the database)
      2) A dictionary of response text, potentially including the key 'main'.
    '''
    task_main = asyncio.create_task(
        llm.get_completion(
            messages=prompts.make_main_prompt(writing),
            extra_args={
                'response_format': {'type': 'json_object'},
            },
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
        "INSERT INTO language_help_queries (writing, user_id, role_id) VALUES (?, ?, ?)",
        [writing, auth.user_id, role_id]
    )
    new_row_id = cur.lastrowid
    db.commit()

    assert new_row_id is not None
    return new_row_id


def record_response(query_id: int, responses: list[dict[str, str]], texts: dict[str, str]) -> None:
    db = get_db()

    db.execute(
        "UPDATE language_help_queries SET response_json=?, response_text=? WHERE id=?",
        [json.dumps(responses), json.dumps(texts), query_id]
    )
    db.commit()


@bp.route("/request", methods=["POST"])
@login_required
@class_enabled_required
@with_llm(spend_token=True)
def help_request(llm: LLM) -> Response:
    writing = request.form["writing"]

    # strip; normalize linebreaks
    lines = writing.strip().splitlines()
    writing = "\n".join(line.rstrip() for line in lines)

    query_id = run_query(llm, writing)

    return redirect(url_for(".help_view", query_id=query_id))
