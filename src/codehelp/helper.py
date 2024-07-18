# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import json
from collections.abc import Iterable
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
from gened.contexts import (
    ContextNotFoundError,
    get_available_contexts,
    get_context_by_name,
)
from gened.db import get_db
from gened.openai import LLMDict, get_completion, with_llm
from gened.queries import get_history, get_query
from gened.testing.mocks import mock_async_completion
from werkzeug.wrappers.response import Response

from . import prompts
from .context import CodeHelpContext

bp = Blueprint('helper', __name__, url_prefix="/help", template_folder='templates')


@bp.route("/")
@bp.route("/retry/<int:query_id>")
@bp.route("/ctx/<int:class_id>/<string:ctx_name>")
@login_required
@class_enabled_required
def help_form(query_id: int | None = None, class_id: int | None = None, ctx_name: str | None = None) -> str | Response:
    db = get_db()
    auth = get_auth()

    if class_id is not None:
        success = switch_class(class_id)
        if not success:
            # Can't access the specified context
            flash(f"Cannot access class and context.  Make sure you are logged in correctly before using this link.", "danger")
            return make_response(render_template("error.html"), 400)

    # we may select a context from a given ctx_name, from a given query_id, or from the user's most recently-used context
    selected_context_name = None
    query_row = None
    if ctx_name is not None:
        # see if the given context is part of the current class (whether available or not)
        try:
            context = get_context_by_name(CodeHelpContext, ctx_name)
            contexts_list = [context]  # this will be the only context in this page -- no other options
            selected_context_name = ctx_name
        except ContextNotFoundError:
            flash(f"Context not found: {ctx_name}", "danger")
            return make_response(render_template("error.html"), 404)
    else:
        contexts_list = get_available_contexts(CodeHelpContext)  # all *available* contexts will be shown
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

    # turn contexts into format we can pass to js via JSON
    contexts = {ctx.name: ctx.desc_html() for ctx in contexts_list}

    # validate selected context name (may no longer exist / be available)
    if selected_context_name not in contexts:
        selected_context_name = None

    # regardless, if there is only one context, select it
    if len(contexts) == 1:
        selected_context_name = next(iter(contexts.keys()))

    history = get_history()

    return render_template("help_form.html", query=query_row, history=history, contexts=contexts, selected_context_name=selected_context_name)


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


def score_response(response_txt: str | None, avoid_set: Iterable[str]) -> int:
    ''' Return an integer score for a given response text.
    Returns:
        0 = best.
        Negative values for responses including indications of code blocks or keywords in the avoid set.
        Indications of code blocks are weighted most heavily.
    '''
    if not response_txt:
        # Empty/None response is pretty bad.
        return -100

    score = 0
    for bad_kw in avoid_set:
        score -= response_txt.count(bad_kw)
    for code_indication in ['```', 'should look like', 'should look something like']:
        score -= 100 * response_txt.count(code_indication)

    return score


async def run_query_prompts(llm_dict: LLMDict, context: CodeHelpContext | None, code: str, error: str, issue: str) -> tuple[list[dict[str, str]], dict[str, str]]:
    ''' Run the given query against the coding help system of prompts.

    Returns a tuple containing:
      1) A list of response objects from the OpenAI completion (to be stored in the database)
      2) A dictionary of response text, potentially including keys 'insufficient' and 'main'.
    '''
    client = llm_dict['client']
    model = llm_dict['model']

    context_str = context.prompt_str() if context is not None else None

    # create "avoid set" from context
    if context is not None and context.avoid:
        avoid_set = {x.strip() for x in context.avoid.split('\n') if x.strip() != ''}
    else:
        avoid_set = set()

    # Launch the "sufficient detail" check concurrently with the main prompt to save time
    task_main = asyncio.create_task(
        get_completion(
            client,
            model=model,
            messages=prompts.make_main_prompt(code, error, issue, context_str),
            n=1,
            score_func=lambda x: score_response(x, avoid_set)
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


def run_query(llm_dict: LLMDict, context: CodeHelpContext | None, code: str, error: str, issue: str) -> int:
    query_id = record_query(context, code, error, issue)

    responses, texts = asyncio.run(run_query_prompts(llm_dict, context, code, error, issue))

    record_response(query_id, responses, texts)

    return query_id


def record_query(context: CodeHelpContext | None, code: str, error: str, issue: str) -> int:
    db = get_db()
    auth = get_auth()
    role_id = auth['role_id']

    context_name = context.name if context is not None else None
    context_str = context.prompt_str() if context is not None else None

    cur = db.execute(
        "INSERT INTO queries (context_name, context, code, error, issue, user_id, role_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [context_name, context_str, code, error, issue, auth['user_id'], role_id]
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
@with_llm()
def help_request(llm_dict: LLMDict) -> Response:
    if 'context' in request.form:
        try:
            context = get_context_by_name(CodeHelpContext, request.form['context'])
        except ContextNotFoundError:
            flash(f"Context not found: {request.form['context']}")
            return make_response(render_template("error.html"), 400)
    else:
        context = None
    code = request.form["code"]
    error = request.form["error"]
    issue = request.form["issue"]

    # TODO: limit length of code/error/issue

    query_id = run_query(llm_dict, context, code, error, issue)

    return redirect(url_for(".help_view", query_id=query_id))


@bp.route("/load_test", methods=["POST"])
@admin_required
@with_llm(use_system_key=True)  # get a populated LLMDict
def load_test(llm_dict: LLMDict) -> Response:
    # Require that we're logged in as the load_test admin user
    auth = get_auth()
    if auth['display_name'] != 'load_test':
        return abort(403)

    context = CodeHelpContext(name="__LOADTEST_Context")
    code = "__LOADTEST_Code"
    error = "__LOADTEST_Error"
    issue = "__LOADTEST_Issue"

    # Monkey-patch to not call the API but simulate it with a delay
    with patch("openai.resources.chat.AsyncCompletions.create") as mocked:
        # simulate a 2 second delay for a network request
        mocked.side_effect = mock_async_completion(delay=2.0)

        query_id = run_query(llm_dict, context, code, error, issue)

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
@with_llm()
def get_topics_html(llm_dict: LLMDict, query_id: int) -> str:
    topics = get_topics(llm_dict, query_id)
    if not topics:
        return render_template("topics_fragment.html", error=True)
    else:
        return render_template("topics_fragment.html", query_id=query_id, topics=topics)


@bp.route("/topics/raw/<int:query_id>", methods=["GET", "POST"])
@login_required
@tester_required
@with_llm()
def get_topics_raw(llm_dict: LLMDict, query_id: int) -> list[str]:
    topics = get_topics(llm_dict, query_id)
    return topics


def get_topics(llm_dict: LLMDict, query_id: int) -> list[str]:
    query_row, responses = get_query(query_id)

    if not query_row or not responses or 'main' not in responses:
        return []

    messages = prompts.make_topics_prompt(
        query_row['context'],
        query_row['code'],
        query_row['error'],
        query_row['issue'],
        responses['main']
    )

    response, response_txt = asyncio.run(get_completion(
        client=llm_dict['client'],
        model=llm_dict['model'],
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
