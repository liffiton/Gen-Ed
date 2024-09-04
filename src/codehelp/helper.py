# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import json
from unittest.mock import patch

from flask import (
    Blueprint,
    abort,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from gened.auth import (
    admin_required,
    class_enabled_required,
    get_auth,
    login_required,
    tester_required,
)
from gened.classes import switch_class
from gened.db import get_db
from gened.openai import LLMConfig, get_completion, with_llm
from gened.queries import get_history, get_query
from gened.testing.mocks import mock_async_completion
from werkzeug.wrappers.response import Response

from . import prompts
from .context import (
    ContextConfig,
    get_available_contexts,
    get_context_by_name,
    record_context_string,
)

bp = Blueprint('helper', __name__, url_prefix="/help", template_folder='templates')


@bp.route("/")
@bp.route("/retry/<int:query_id>")
@bp.route("/ctx/<int:class_id>/<string:ctx_name>")
@login_required
@class_enabled_required
@with_llm(spend_token=False)  # get information on the selected LLM, tokens remaining
def help_form(llm: LLMConfig, query_id: int | None = None, class_id: int | None = None, ctx_name: str | None = None) -> str | Response:
    db = get_db()
    auth = get_auth()

    if class_id is not None:
        success = switch_class(class_id)
        if not success:
            # Can't access the specified context
            flash("Cannot access class and context.  Make sure you are logged in correctly before using this link.", "danger")
            return make_response(render_template("error.html"), 400)

    # we may select a context from a given ctx_name, from a given query_id, or from the user's most recently-used context
    selected_context_name = None
    query_row = None
    if ctx_name is not None:
        # see if the given context is part of the current class (whether available or not)
        context = get_context_by_name(ctx_name)
        if context is None:
            flash(f"Context not found: {ctx_name}", "danger")
            return make_response(render_template("error.html"), 404)
        contexts_list = [context]  # this will be the only context in this page -- no other options
        selected_context_name = ctx_name
    else:
        contexts_list = get_available_contexts()  # all *available* contexts will be shown
        if query_id is not None:
            # populate with a query if one is specified in the query string
            query_row, _ = get_query(query_id)   # _ because we don't need responses here
            if query_row is not None:
                selected_context_name = query_row['context_name']
        else:
            # no query specified,
            # but we can pre-select the most recently used context, if available
            recent_row = db.execute("SELECT context_name FROM queries WHERE queries.user_id=? ORDER BY id DESC LIMIT 1", [auth['user_id']]).fetchone()
            if recent_row:
                selected_context_name = recent_row['context_name']

        # verify the context is real and part of the current class
        if selected_context_name is not None:
            context = get_context_by_name(selected_context_name)
            if context is None:
                selected_context_name = None
            else:
                contexts_list.append(context)  # add this context to the list - may be hidden - if duplicate, dict comprehension will automatically filter

    # turn contexts into format we can pass to js via JSON
    contexts = {ctx.name: ctx.desc_html() for ctx in contexts_list}

    # regardless, if there is only one context, select it
    if len(contexts) == 1:
        selected_context_name = next(iter(contexts.keys()))

    history = get_history()

    return render_template("help_form.html", llm=llm, query=query_row, history=history, contexts=contexts, selected_context_name=selected_context_name)


@bp.route("/view/<int:query_id>")
@login_required
def help_view(query_id: int) -> str | Response:
    query_row, responses = get_query(query_id)

    if query_row is None:
        return make_response(render_template("error.html"), 400)

    history = get_history()
    if query_row and query_row['topics_json']:
        topics = json.loads(query_row['topics_json'])
    else:
        topics = []

    return render_template("help_view.html", query=query_row, responses=responses, history=history, topics=topics)


async def run_query_prompts(llm: LLMConfig, context: ContextConfig | None, code: str, error: str, issue: str) -> tuple[list[dict[str, str]], dict[str, str]]:
    ''' Run the given query against the coding help system of prompts.

    Returns a tuple containing:
      1) A list of response objects from the OpenAI completion (to be stored in the database)
      2) A dictionary of response text, potentially including keys 'insufficient' and 'main'.
    '''
    client = llm.client
    model = llm.model

    context_str = context.prompt_str() if context is not None else None

    # Launch the "sufficient detail" check concurrently with the main prompt to save time
    task_main = asyncio.create_task(
        get_completion(
            client,
            model=model,
            messages=prompts.make_main_prompt(code, error, issue, context_str),
        )
    )
    task_sufficient = asyncio.create_task(
        get_completion(
            client,
            model=model,
            messages=prompts.make_sufficient_prompt(code, error, issue, context_str),
        )
    )

    # Store all responses received
    responses = []

    # Let's get the main response.
    response_main, response_txt = await task_main
    responses.append(response_main)

    if "```" in response_txt or "should look like" in response_txt or "should look something like" in response_txt:
        # That's probably too much code.  Let's clean it up...
        cleanup_prompt = prompts.make_cleanup_prompt(response_text=response_txt)
        cleanup_response, cleanup_response_txt = await get_completion(client, model, prompt=cleanup_prompt)
        responses.append(cleanup_response)
        response_txt = cleanup_response_txt

    # Check whether there is sufficient information
    # Checking after processing main+cleanup prevents this from holding up the start of cleanup if this was slow
    response_sufficient, response_sufficient_txt = await task_sufficient
    responses.append(response_sufficient)

    if 'error' in response_main:
        return responses, {'error': response_txt}
    elif response_sufficient_txt.endswith("OK") or "OK." in response_sufficient_txt or "```" in response_sufficient_txt or "is sufficient for me" in response_sufficient_txt or response_sufficient_txt.startswith("Error ("):
        # We're using just the main response.
        return responses, {'main': response_txt}
    else:
        # Give them the request for more information plus the main response, in case it's helpful.
        return responses, {'insufficient': response_sufficient_txt, 'main': response_txt}


def run_query(llm: LLMConfig, context: ContextConfig | None, code: str, error: str, issue: str) -> int:
    query_id = record_query(context, code, error, issue)

    responses, texts = asyncio.run(run_query_prompts(llm, context, code, error, issue))

    record_response(query_id, responses, texts)

    return query_id


def record_query(context: ContextConfig | None, code: str, error: str, issue: str) -> int:
    db = get_db()
    auth = get_auth()
    role_id = auth['role_id']

    if context is not None:
        context_name = context.name
        context_str = context.prompt_str()
        context_string_id = record_context_string(context_str)
    else:
        context_name = None
        context_string_id = None

    cur = db.execute(
        "INSERT INTO queries (context_name, context_string_id, code, error, issue, user_id, role_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [context_name, context_string_id, code, error, issue, auth['user_id'], role_id]
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
@with_llm(spend_token=True)
def help_request(llm: LLMConfig) -> Response:
    if 'context' in request.form:
        context = get_context_by_name(request.form['context'])
        if context is None:
            flash(f"Context not found: {request.form['context']}")
            return make_response(render_template("error.html"), 400)
    else:
        context = None
    code = request.form["code"]
    error = request.form["error"]
    issue = request.form["issue"]

    # TODO: limit length of code/error/issue

    query_id = run_query(llm, context, code, error, issue)

    return redirect(url_for(".help_view", query_id=query_id))


@bp.route("/load_test", methods=["POST"])
@admin_required
@with_llm(use_system_key=True)  # get a populated LLMConfig; not actually used (API is mocked)
def load_test(llm: LLMConfig) -> Response:
    # Require that we're logged in as the load_test admin user
    auth = get_auth()
    if auth['display_name'] != 'load_test':
        return abort(403)

    context = ContextConfig(name="__LOADTEST_Context")
    code = "__LOADTEST_Code"
    error = "__LOADTEST_Error"
    issue = "__LOADTEST_Issue"

    # Monkey-patch to not call the API but simulate it with a delay
    with patch("openai.resources.chat.AsyncCompletions.create") as mocked:
        # simulate a 2 second delay for a network request
        mocked.side_effect = mock_async_completion(delay=2.0)

        query_id = run_query(llm, context, code, error, issue)

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


@bp.route("/topics/html/<int:query_id>", methods=["GET", "POST"])
@login_required
@tester_required
@with_llm(spend_token=False)
def get_topics_html(llm: LLMConfig, query_id: int) -> str:
    topics = get_topics(llm, query_id)
    if not topics:
        return render_template("topics_fragment.html", error=True)
    else:
        return render_template("topics_fragment.html", query_id=query_id, topics=topics)


@bp.route("/topics/raw/<int:query_id>", methods=["GET", "POST"])
@login_required
@tester_required
@with_llm(spend_token=False)
def get_topics_raw(llm: LLMConfig, query_id: int) -> list[str]:
    topics = get_topics(llm, query_id)
    return topics


def get_topics(llm: LLMConfig, query_id: int) -> list[str]:
    query_row, responses = get_query(query_id)

    if not query_row or not responses or 'main' not in responses:
        return []

    messages = prompts.make_topics_prompt(
        query_row['code'],
        query_row['error'],
        query_row['issue'],
        '',  # TODO: put this back: query_row['context'],
        responses['main']
    )

    response, response_txt = asyncio.run(get_completion(
        client=llm.client,
        model=llm.model,
        messages=messages,
    ))

    # Verify it is actually JSON
    # May be "Error (..." if an API error occurs, or every now and then may get "Here is the JSON: ..." or similar.
    try:
        topics: list[str] = json.loads(response_txt)
    except json.decoder.JSONDecodeError:
        return []

    # Save topics into queries table for the given query
    db = get_db()
    db.execute("UPDATE queries SET topics_json=? WHERE id=?", [response_txt, query_id])
    db.commit()
    return topics
