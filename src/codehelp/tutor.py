# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import json
from sqlite3 import Row

from flask import (
    Blueprint,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from gened.admin import bp as bp_admin
from gened.admin import register_admin_link
from gened.auth import get_auth, login_required
from gened.classes import switch_class
from gened.db import get_db
from gened.experiments import experiment_required
from gened.openai import LLMConfig, get_completion, with_llm
from gened.queries import get_query
from openai.types.chat import ChatCompletionMessageParam
from werkzeug.wrappers.response import Response

from . import prompts
from .context import (
    ContextConfig,
    get_available_contexts,
    get_context_by_name,
    record_context_string,
)


class ChatNotFoundError(Exception):
    pass


class AccessDeniedError(Exception):
    pass


bp = Blueprint('tutor', __name__, url_prefix="/tutor", template_folder='templates')


@bp.before_request
@experiment_required("chats_experiment")
@login_required
def before_request() -> None:
    """Apply decorators to protect all tutor blueprint endpoints.
    Use @experiment_required first so that non-logged-in users get a 404 as well.
    """


@bp.route("/")
@bp.route("/ctx/<int:class_id>/<string:ctx_name>")
def tutor_form(class_id: int | None = None, ctx_name: str | None = None) -> str | Response:

    if class_id is not None:
        success = switch_class(class_id)
        if not success:
            # Can't access the specified context
            flash("Cannot access class and context.  Make sure you are logged in correctly before using this link.", "danger")
            return make_response(render_template("error.html"), 400)

    # we may select a context from a given ctx_name, from a given query_id, or from the user's most recently-used context
    selected_context_name = None
    if ctx_name is not None:
        # see if the given context is part of the current class (whether available or not)
        context = get_context_by_name(ctx_name)
        if context is None:
            flash(f"Context not found: {ctx_name}", "danger")
            return make_response(render_template("error.html"), 404)
        contexts_list = [context]  # this will be the only context in this page -- no other options
        selected_context_name = ctx_name
    else:
        contexts_list = get_available_contexts()

    # turn into format we can pass to js via JSON
    contexts = {ctx.name: ctx.desc_html() for ctx in contexts_list}

    # regardless, if there is only one context, select it
    if len(contexts) == 1:
        selected_context_name = next(iter(contexts.keys()))

    chat_history = get_chat_history()
    return render_template("tutor_new_form.html", contexts=contexts, selected_context_name=selected_context_name, chat_history=chat_history)


@bp.route("/chat/create", methods=["POST"])
@with_llm()
def start_chat(llm: LLMConfig) -> Response:
    topic = request.form['topic']

    if 'context' in request.form:
        context = get_context_by_name(request.form['context'])
        if context is None:
            flash(f"Context not found: {request.form['context']}")
            return make_response(render_template("error.html"), 400)
    else:
        context = None

    chat_id = create_chat(topic, context)

    run_chat_round(llm, chat_id)

    return redirect(url_for("tutor.chat_interface", chat_id=chat_id))


@bp.route("/chat/create_from_query", methods=["POST"])
@with_llm()
def start_chat_from_query(llm: LLMConfig) -> Response:
    topic = request.form['topic']

    # build context from the specified query
    query_id = int(request.form['query_id'])
    query_row, response = get_query(query_id)
    assert query_row
    context = get_context_by_name(query_row['context_name'])

    chat_id = create_chat(topic, context)

    run_chat_round(llm, chat_id)

    return redirect(url_for("tutor.chat_interface", chat_id=chat_id))


@bp.route("/chat/<int:chat_id>")
def chat_interface(chat_id: int) -> str | Response:
    try:
        chat, topic, context_name, context_string = get_chat(chat_id)
    except (ChatNotFoundError, AccessDeniedError):
        flash("Invalid id.", "warning")
        return make_response(render_template("error.html"), 400)

    chat_history = get_chat_history()

    return render_template("tutor_view.html", chat_id=chat_id, topic=topic, context_name=context_name, chat=chat, chat_history=chat_history)


def create_chat(topic: str, context: ContextConfig | None) -> int:
    db = get_db()
    auth = get_auth()
    user_id = auth['user_id']
    role_id = auth['role_id']

    if context is not None:
        context_name = context.name
        context_string_id = record_context_string(context.prompt_str())
    else:
        context_name = None
        context_string_id = None

    cur = db.execute(
        "INSERT INTO chats (user_id, role_id, topic, context_name, context_string_id, chat_json) VALUES (?, ?, ?, ?, ?, ?)",
        [user_id, role_id, topic, context_name, context_string_id, json.dumps([])]
    )
    new_row_id = cur.lastrowid

    db.commit()

    assert new_row_id is not None
    return new_row_id


def get_chat_history(limit: int = 10) -> list[Row]:
    '''Fetch current user's chat history.'''
    db = get_db()
    auth = get_auth()

    history = db.execute("SELECT * FROM chats WHERE user_id=? ORDER BY id DESC LIMIT ?", [auth['user_id'], limit]).fetchall()
    return history


def get_chat(chat_id: int) -> tuple[list[ChatCompletionMessageParam], str, str, str]:
    db = get_db()
    auth = get_auth()

    chat_row = db.execute(
        "SELECT chat_json, topic, context_name, context_strings.ctx_str AS context_string, chats.user_id, roles.class_id "
        "FROM chats "
        "JOIN users ON chats.user_id=users.id "
        "LEFT JOIN roles ON chats.role_id=roles.id "
        "LEFT JOIN context_strings ON chats.context_string_id=context_strings.id "
        "WHERE chats.id=?",
        [chat_id]
    ).fetchone()

    if not chat_row:
        raise ChatNotFoundError

    access_allowed = \
        (auth['user_id'] == chat_row['user_id']) \
        or auth['is_admin'] \
        or (auth['role'] == 'instructor' and auth['class_id'] == chat_row['class_id'])

    if not access_allowed:
        raise AccessDeniedError

    chat_json = chat_row['chat_json']
    chat = json.loads(chat_json)
    topic = chat_row['topic']
    context_name = chat_row['context_name']
    context_string = chat_row['context_string']

    return chat, topic, context_name, context_string


def get_response(llm: LLMConfig, chat: list[ChatCompletionMessageParam]) -> tuple[dict[str, str], str]:
    ''' Get a new 'assistant' completion for the specified chat.

    Parameters:
      - chat: A list of dicts, each containing a message with 'role' and 'content' keys,
              following the OpenAI chat completion API spec.

    Returns a tuple containing:
      1) A response object from the OpenAI completion (to be stored in the database).
      2) The response text.
    '''
    response, text = asyncio.run(get_completion(
        client=llm.client,
        model=llm.model,
        messages=chat,
    ))

    return response, text


def save_chat(chat_id: int, chat: list[ChatCompletionMessageParam]) -> None:
    db = get_db()
    db.execute(
        "UPDATE chats SET chat_json=? WHERE id=?",
        [json.dumps(chat), chat_id]
    )
    db.commit()


def run_chat_round(llm: LLMConfig, chat_id: int, message: str|None = None) -> None:
    # Get the specified chat
    try:
        chat, topic, context_name, context_string = get_chat(chat_id)
    except (ChatNotFoundError, AccessDeniedError):
        return

    # Add the new message to the chat
    if message is not None:
        chat.append({
            'role': 'user',
            'content': message,
        })

    save_chat(chat_id, chat)

    # Get a response (completion) from the API using an expanded version of the chat messages
    # Insert a system prompt beforehand and an internal monologue after to guide the assistant
    expanded_chat : list[ChatCompletionMessageParam] = [
        {'role': 'system', 'content': prompts.make_chat_sys_prompt(topic, context_string)},
        *chat,  # chat is a list; expand it here with *
        {'role': 'assistant', 'content': prompts.tutor_monologue},
    ]

    response_obj, response_txt = get_response(llm, expanded_chat)

    # Update the chat w/ the response
    chat.append({
        'role': 'assistant',
        'content': response_txt,
    })
    save_chat(chat_id, chat)


@bp.route("/message", methods=["POST"])
@with_llm()
def new_message(llm: LLMConfig) -> Response:
    chat_id = int(request.form["id"])
    new_msg = request.form["message"]

    # TODO: limit length

    # Run a round of the chat with the given message.
    run_chat_round(llm, chat_id, new_msg)

    # Send the user back to the now-updated chat view
    return redirect(url_for("tutor.chat_interface", chat_id=chat_id))


# ### Admin routes ###

@register_admin_link("Tutor Chats")
@bp_admin.route("/tutor/")
@bp_admin.route("/tutor/<int:chat_id>")
def tutor_admin(chat_id : int|None = None) -> str:
    db = get_db()
    chats = db.execute("""
        SELECT
            chats.id,
            users.display_name,
            chats.topic,
            (
                SELECT
                    COUNT(*)
                FROM
                    json_each(chats.chat_json)
                WHERE
                    json_extract(json_each.value, '$.role')='user'
            ) as user_msgs
        FROM
            chats
        JOIN
            users ON chats.user_id=users.id
        ORDER BY
            chats.id DESC
    """).fetchall()

    if chat_id is not None:
        chat_row = db.execute("SELECT users.display_name, topic, chat_json FROM chats JOIN users ON chats.user_id=users.id WHERE chats.id=?", [chat_id]).fetchone()
        chat = json.loads(chat_row['chat_json'])
    else:
        chat_row = None
        chat = None

    return render_template("tutor_admin.html", chats=chats, chat_row=chat_row, chat=chat)
