# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import json
from dataclasses import asdict, dataclass
from sqlite3 import Row
from typing import Any, Literal, TypeAlias

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

from codehelp.contexts import (
    ContextConfig,
    get_available_contexts,
    get_context_by_name,
)
from gened.auth import class_enabled_required, get_auth, login_required
from gened.classes import switch_class
from gened.db import get_db
from gened.experiments import experiment_required
from gened.llm import LLM, ChatMessage, with_llm

from . import prompts
from .guided import TutorConfig


class ChatNotFoundError(Exception):
    pass


class AccessDeniedError(Exception):
    pass


ChatMode: TypeAlias = Literal["inquiry", "guided"]

@dataclass
class ChatData:
    topic: str
    context_name: str | None
    messages: list[ChatMessage]
    mode: ChatMode
    analysis: dict[str, Any] | None = None


bp = Blueprint('chat', __name__, url_prefix="/chat", template_folder='templates')


@bp.before_request
@experiment_required("chats_experiment")
@login_required
def before_request() -> None:
    """Apply decorators to protect all tutor blueprint endpoints.
    Use @experiment_required first so that non-logged-in users get a 404 as well.
    """


@bp.route("/new")
def new_chat_form() -> str:
    contexts_list = get_available_contexts()
    # turn into format we can pass to js via JSON
    contexts = {ctx.name: ctx.desc_html() for ctx in contexts_list}

    # get pre-defined guided chat tutors
    tutors = []
    db = get_db()
    auth = get_auth()
    if auth.cur_class:
        tutor_rows = db.execute("SELECT * FROM tutors WHERE class_id=?", [auth.cur_class.class_id]).fetchall()
        tutors = [json.loads(row['config']) | {'id': row['id']} for row in tutor_rows]

    recent_chats = get_chat_history()
    return render_template("tutor_new_form.html", contexts=contexts, tutors=tutors, recent_chats=recent_chats)


@bp.route("/new/ctx/<int:class_id>/<string:ctx_name>")
def new_inquiry_chat_form(class_id: int, ctx_name: str) -> str | Response:
    success = switch_class(class_id)
    if not success:
        # Can't access the specified context
        flash("Cannot access class and context.  Make sure you are logged in correctly before using this link.", "danger")
        return make_response(render_template("error.html"), 400)

    context = get_context_by_name(ctx_name)
    if not context:
        flash(f"Context not found: {ctx_name}", "danger")
        return make_response(render_template("error.html"), 404)
    contexts_list = [context]

    # turn into format we can pass to js via JSON
    contexts = {ctx.name: ctx.desc_html() for ctx in contexts_list}

    recent_chats = get_chat_history()
    return render_template("tutor_new_form.html", contexts=contexts, recent_chats=recent_chats)


@bp.route("/create_inquiry", methods=["POST"])
@class_enabled_required
@with_llm()
def create_inquiry_chat(llm: LLM) -> Response:
    topic = request.form['topic']
    context: ContextConfig | None = None

    if context_name := request.form.get('context'):
        context = get_context_by_name(context_name)
        if context is None:
            flash(f"Context not found: {context_name}", "danger")
            return make_response(render_template("error.html"), 400)

    context_name = context.name if context else None
    context_string = context.prompt_str() if context else None
    sys_prompt = prompts.inquiry_sys_msg_tpl.render(topic=topic, context=context_string)

    chat_id = _create_chat(topic, context_name, sys_prompt, "inquiry")

    run_chat_round(llm, chat_id)

    return redirect(url_for("tutors.chat.chat_interface", chat_id=chat_id))


@bp.route("/create_guided", methods=["POST"])
@class_enabled_required
@with_llm()
def create_guided_chat(llm: LLM) -> Response:
    db = get_db()
    auth = get_auth()
    assert auth.cur_class is not None
    tutor_id = request.form['tutor_id']
    row = db.execute("SELECT * FROM tutors WHERE class_id=? AND id=?", [auth.cur_class.class_id, tutor_id]).fetchone()

    tutor_config = TutorConfig.from_dict(json.loads(row['config']))

    sys_prompt = prompts.guided_sys_msg_tpl.render(tutor_config=tutor_config)

    chat_id = _create_chat(tutor_config.topic, context_name=None, sys_prompt=sys_prompt, mode="guided")

    run_chat_round(llm, chat_id)

    return redirect(url_for("tutors.chat.chat_interface", chat_id=chat_id))


def _create_chat(topic: str, context_name: str | None, sys_prompt: str, mode: ChatMode) -> int:
    db = get_db()
    auth = get_auth()
    user_id = auth.user_id
    role_id = auth.cur_class.role_id if auth.cur_class else None

    messages : list[ChatMessage] = [
        {'role': 'system', 'content': sys_prompt},
    ]
    chat_data = ChatData(
        topic=topic,
        context_name=context_name,
        messages=messages,
        mode=mode,
    )

    cur = db.execute(
        "INSERT INTO chats (user_id, role_id, chat_json) VALUES (?, ?, ?)",
        [user_id, role_id, json.dumps(asdict(chat_data))]
    )
    new_row_id = cur.lastrowid

    db.commit()

    assert new_row_id is not None
    return new_row_id


@bp.route("/<int:chat_id>")
def chat_interface(chat_id: int) -> str | Response:
    try:
        chat_data = get_chat(chat_id)
    except (ChatNotFoundError, AccessDeniedError):
        abort(400, "Invalid id.")

    recent_chats = get_chat_history()

    return render_template("tutor_view.html", chat_id=chat_id, chat=chat_data, recent_chats=recent_chats)


def get_chat_history(limit: int = 10) -> list[Row]:
    '''Fetch current user's chat history.'''
    db = get_db()
    auth = get_auth()

    history = db.execute("SELECT id, json_extract(chat_json, '$.topic') AS topic FROM chats WHERE user_id=? ORDER BY id DESC LIMIT ?", [auth.user_id, limit]).fetchall()
    return history


def get_chat(chat_id: int) -> ChatData:
    db = get_db()
    auth = get_auth()

    chat_row = db.execute(
        "SELECT chat_json, chats.user_id, roles.class_id "
        "FROM chats "
        "JOIN users ON chats.user_id=users.id "
        "LEFT JOIN roles ON chats.role_id=roles.id "
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
    chat_data = json.loads(chat_json)

    return ChatData(**chat_data)


def save_chat(chat_id: int, chat_data: ChatData) -> None:
    db = get_db()
    db.execute(
        "UPDATE chats SET chat_json=? WHERE id=?",
        [json.dumps(asdict(chat_data)), chat_id]
    )
    db.commit()


def run_chat_round(llm: LLM, chat_id: int, user_message: str|None = None) -> None:
    # Get the specified chat
    try:
        chat = get_chat(chat_id)
    except (ChatNotFoundError, AccessDeniedError):
        return

    messages = chat.messages

    # Add the new message to the chat (persisting to the DB)
    if user_message is not None:
        messages.append({
            'role': 'user',
            'content': user_message,
        })
        save_chat(chat_id, chat)

    if chat.mode == "guided":
        # Summarize/analyze the chat so far
        analyze_messages: list[ChatMessage] = [
            *messages,
            {'role': 'system', 'content': prompts.guided_analyze_tpl.render(chat=chat)},
        ]
        analyze_response, analyze_response_txt = asyncio.run(llm.get_completion(
            messages=analyze_messages,
            extra_args={
                #'reasoning_effort': 'none',  # for thinking models: o3/o4/gemini-2.5
                'response_format': {'type': 'json_object'},
            },
        ))
        analysis = json.loads(analyze_response_txt)
        chat.analysis = analysis

    # Generate a response
    response, response_txt = asyncio.run(llm.get_completion(messages=messages))

    # Update the chat w/ the response (and persist to the DB)
    messages.append({
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
