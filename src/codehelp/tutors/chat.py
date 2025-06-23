# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import json
from dataclasses import dataclass
from sqlite3 import Row

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
from werkzeug.wrappers.response import Response

import gened.admin
from codehelp.contexts import (
    ContextConfig,
    get_available_contexts,
    get_context_by_name,
    record_context_string,
)
from gened.auth import get_auth, login_required
from gened.classes import switch_class
from gened.db import get_db
from gened.experiments import experiment_required
from gened.llm import LLM, ChatMessage, with_llm
from gened.tables import Col, DataTable, NumCol

from . import prompts


class ChatNotFoundError(Exception):
    pass


class AccessDeniedError(Exception):
    pass


@dataclass(frozen=True)
class ChatData:
    chat: list[ChatMessage]
    topic: str
    context_name: str | None
    context_string: str | None


bp = Blueprint('chat', __name__, url_prefix="/chat", template_folder='templates')


@bp.before_request
@experiment_required("chats_experiment")
@login_required
def before_request() -> None:
    """Apply decorators to protect all tutor blueprint endpoints.
    Use @experiment_required first so that non-logged-in users get a 404 as well.
    """


@bp.route("/new")
@bp.route("/new/ctx/<int:class_id>/<string:ctx_name>")
def new_chat(class_id: int | None = None, ctx_name: str | None = None) -> str | Response:

    if class_id is not None:
        success = switch_class(class_id)
        if not success:
            # Can't access the specified context
            flash("Cannot access class and context.  Make sure you are logged in correctly before using this link.", "danger")
            return make_response(render_template("error.html"), 400)

    selected_context_name = ctx_name
    if ctx_name:
        context = get_context_by_name(ctx_name)
        if not context:
            flash(f"Context not found: {ctx_name}", "danger")
            return make_response(render_template("error.html"), 404)
        contexts_list = [context]
    else:
        contexts_list = get_available_contexts()
        if len(contexts_list) == 1:
            selected_context_name = contexts_list[0].name

    # turn into format we can pass to js via JSON
    contexts = {ctx.name: ctx.desc_html() for ctx in contexts_list}

    chat_history = get_chat_history()
    return render_template("tutor_new_form.html", contexts=contexts, selected_context_name=selected_context_name, chat_history=chat_history)


@bp.route("/create", methods=["POST"])
@with_llm()
def start_chat(llm: LLM) -> Response:
    topic = request.form['topic']
    context: ContextConfig | None = None

    if context_name := request.form.get('context'):
        context = get_context_by_name(context_name)
        if context is None:
            flash(f"Context not found: {context_name}", "danger")
            return make_response(render_template("error.html"), 400)

    chat_id = create_chat(topic, context)

    run_chat_round(llm, chat_id)

    return redirect(url_for("tutors.chat.chat_interface", chat_id=chat_id))


@bp.route("/<int:chat_id>")
def chat_interface(chat_id: int) -> str | Response:
    try:
        chat_data = get_chat(chat_id)
    except (ChatNotFoundError, AccessDeniedError):
        abort(400, "Invalid id.")

    chat_history = get_chat_history()

    return render_template("tutor_view.html", chat_id=chat_id, topic=chat_data.topic, context_name=chat_data.context_name, chat=chat_data.chat, chat_history=chat_history)


def create_chat(topic: str, context: ContextConfig | None) -> int:
    db = get_db()
    auth = get_auth()
    user_id = auth.user_id
    role_id = auth.cur_class.role_id if auth.cur_class else None

    context_name = context.name if context else None
    context_string_id = record_context_string(context.prompt_str()) if context else None

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

    history = db.execute("SELECT * FROM chats WHERE user_id=? ORDER BY id DESC LIMIT ?", [auth.user_id, limit]).fetchall()
    return history


def get_chat(chat_id: int) -> ChatData:
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

    is_owner = auth.user_id == chat_row['user_id']
    is_instructor_in_class = (
        auth.cur_class
        and auth.cur_class.role == 'instructor'
        and auth.cur_class.class_id == chat_row['class_id']
    )
    access_allowed = is_owner or is_instructor_in_class or auth.is_admin

    if not access_allowed:
        raise AccessDeniedError

    chat_json = chat_row['chat_json']
    chat = json.loads(chat_json)
    topic = chat_row['topic']
    context_name = chat_row['context_name']
    context_string = chat_row['context_string']

    return ChatData(chat, topic, context_name, context_string)


def get_response(llm: LLM, chat: list[ChatMessage]) -> tuple[dict[str, str], str]:
    ''' Get a new 'assistant' completion for the specified chat.

    Parameters:
      - chat: A list of dicts, each containing a message with 'role' and 'content' keys,
              following the OpenAI chat completion API spec.

    Returns a tuple containing:
      1) A response object from the LLM completion (to be stored in the database).
      2) The response text.
    '''
    response, text = asyncio.run(llm.get_completion(messages=chat))

    return response, text


def save_chat(chat_id: int, chat: list[ChatMessage]) -> None:
    db = get_db()
    db.execute(
        "UPDATE chats SET chat_json=? WHERE id=?",
        [json.dumps(chat), chat_id]
    )
    db.commit()


def run_chat_round(llm: LLM, chat_id: int, message: str|None = None) -> None:
    # Get the specified chat
    try:
        chat_data = get_chat(chat_id)
    except (ChatNotFoundError, AccessDeniedError):
        return

    chat = chat_data.chat

    # Add the new message to the chat
    if message is not None:
        chat.append({
            'role': 'user',
            'content': message,
        })

    save_chat(chat_id, chat)

    # Get a response (completion) from the API using an expanded version of the chat messages
    # Insert a system prompt beforehand and an internal monologue after to guide the assistant
    expanded_chat : list[ChatMessage] = [
        {'role': 'system', 'content': prompts.chat_template_sys.render(topic=chat_data.topic, context=chat_data.context_string)},
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


@bp.route("/post_message", methods=["POST"])
@with_llm()
def new_message(llm: LLM) -> Response:
    chat_id = int(request.form["id"])
    new_msg = request.form["message"]

    # TODO: limit length

    # Run a round of the chat with the given message.
    run_chat_round(llm, chat_id, new_msg)

    # Send the user back to the now-updated chat view
    return redirect(url_for("tutors.chat.chat_interface", chat_id=chat_id))


# ### Admin routes ###
bp_admin = Blueprint('admin_tutor', __name__, url_prefix='/tutor', template_folder='templates')

# Register the tutors admin component.
gened.admin.register_blueprint(bp_admin)
gened.admin.register_navbar_item("admin_tutor.tutor_admin", "Tutor Chats")


@bp_admin.route("/")
@bp_admin.route("/<int:chat_id>")
def tutor_admin(chat_id : int|None = None) -> str:
    db = get_db()
    chats = db.execute("""
        SELECT
            chats.id AS id,
            users.display_name AS user,
            chats.topic AS topic,
            (
                SELECT COUNT(*)
                FROM json_each(chats.chat_json)
                WHERE json_extract(json_each.value, '$.role')='user'
            ) as "user messages"
        FROM chats
        JOIN users ON chats.user_id=users.id
        ORDER BY chats.id DESC
    """).fetchall()

    table = DataTable(
        name='chats',
        columns=[NumCol('id'), Col('user'), Col('topic'), NumCol('user messages')],
        link_col=0,
        link_template='${value}',
        data=chats,
    )

    if chat_id is not None:
        chat_row = db.execute("SELECT users.display_name, topic, chat_json FROM chats JOIN users ON chats.user_id=users.id WHERE chats.id=?", [chat_id]).fetchone()
        chat = json.loads(chat_row['chat_json'])
    else:
        chat_row = None
        chat = None

    return render_template("tutor_admin.html", chats=table, chat_row=chat_row, chat=chat)
