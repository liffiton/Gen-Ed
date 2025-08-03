# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import json
from dataclasses import asdict

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

from components.code_contexts import (
    ContextConfig,
    get_available_contexts,
    get_context_by_name,
)
from gened.app_data import DataAccessError
from gened.auth import class_enabled_required, get_auth, login_required
from gened.classes import switch_class
from gened.db import get_db
from gened.experiments import experiment_required
from gened.llm import LLM, ChatMessage, with_llm

from . import prompts
from .data import ChatData, ChatMode, chats_data_source
from .guided import TutorConfig

bp = Blueprint('tutors', __name__, url_prefix='/tutor', template_folder='templates')


@bp.before_request
@experiment_required("chats_experiment")
@login_required
def before_request() -> None:
    """Apply decorators to protect all tutor blueprint endpoints.
    Use @experiment_required first so that non-logged-in users get a 404 as well.
    """


@bp.route("/new")
@bp.route("/new/<int:class_id>")
def new_chat_form(class_id: int | None = None) -> Response | str:
    db = get_db()
    auth = get_auth()

    if class_id is not None:
        success = switch_class(class_id)
        if not success:
            # Can't access the specified class
            flash("Cannot access specified class.  Make sure you are logged in correctly before using this link.", "danger")
            return make_response(render_template("error.html"), 400)

        contexts = None
        tutor_rows = None

        if 'ctx_name' in request.args:
            ctx_name = request.args['ctx_name']
            context = get_context_by_name(ctx_name)
            if not context:
                flash(f"Context not found: '{ctx_name}'", "danger")
                return make_response(render_template("error.html"), 400)
            contexts = {context.name: context.desc_html()}
        elif 'tutor_name' in request.args:
            tutor_name = request.args['tutor_name']
            tutor_rows = db.execute("SELECT id, name FROM tutors WHERE class_id=? AND name=?", [class_id, tutor_name]).fetchall()
            if not tutor_rows:
                flash(f"Tutor not found: '{tutor_name}'", "danger")
                return make_response(render_template("error.html"), 400)
        else:
            return make_response(render_template("error.html"), 400)

    else:
        # All contexts and all guided tutors
        contexts_list = get_available_contexts()
        # turn into format we can pass to js via JSON
        contexts = {ctx.name: ctx.desc_html() for ctx in contexts_list}

        # Get all pre-defined guided tutors that are available:
        #   current date anywhere on earth (using UTC+12) is at or after the saved date
        class_id = auth.cur_class.class_id if auth.cur_class else None
        tutor_rows = db.execute("SELECT id, name FROM tutors WHERE class_id=? AND available <= date('now', '+12 hours') ORDER BY class_order ASC", [class_id]).fetchall()

    recent_chats = chats_data_source.get_user_data(limit=10)

    return render_template("tutor_new_form.html", contexts=contexts, tutors=tutor_rows, recent_chats=recent_chats)


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
    auth = get_auth()
    tikz_enabled = 'tikz_experiment' in auth.class_experiments
    sys_prompt = prompts.inquiry_sys_msg_tpl.render(topic=topic, context=context_string, tikz_enabled=tikz_enabled)

    chat_id = _create_chat(topic, context_name, sys_prompt, "inquiry")

    run_chat_round(llm, chat_id)

    return redirect(url_for("tutors.chat_interface", chat_id=chat_id))


@bp.route("/create_guided", methods=["POST"])
@class_enabled_required
@with_llm()
def create_guided_chat(llm: LLM) -> Response:
    db = get_db()
    auth = get_auth()
    assert auth.cur_class is not None
    tutor_id = request.form['tutor_id']
    row = db.execute("SELECT * FROM tutors WHERE class_id=? AND id=?", [auth.cur_class.class_id, tutor_id]).fetchone()

    tutor_config = TutorConfig.from_row(row)

    auth = get_auth()
    tikz_enabled = 'tikz_experiment' in auth.class_experiments
    sys_prompt = prompts.guided_sys_msg_tpl.render(tutor_config=tutor_config, tikz_enabled=tikz_enabled)

    chat_id = _create_chat(tutor_config.topic, context_name=None, sys_prompt=sys_prompt, mode="guided")

    run_chat_round(llm, chat_id)

    return redirect(url_for("tutors.chat_interface", chat_id=chat_id))


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
    except DataAccessError:
        abort(400, "Invalid id.")

    recent_chats = chats_data_source.get_user_data(limit=10)

    return render_template("tutor_view.html", chat_id=chat_id, chat=chat_data, recent_chats=recent_chats)


def get_chat(chat_id: int) -> ChatData:
    chat_row = chats_data_source.get_row(chat_id)

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
    except DataAccessError:
        return

    messages = chat.messages

    if user_message is not None:
        # Add the new message to the chat (persisting to the DB) and generate a response
        messages.append({
            'role': 'user',
            'content': user_message,
        })
        save_chat(chat_id, chat)
        # Generate a response
        response, response_txt = asyncio.run(llm.get_completion(messages=messages))
    else:
        # Gemini, at least, requires a user message to start, but we don't need
        # to save or display it, so make a copy of the messages rather than
        # updating the messages in the `chat` object.
        msgs_copy = messages[:]
        msgs_copy.append({
            'role': 'user',
            'content': 'Please generate an initial message for the user.',
        })
        # Generate a response
        response, response_txt = asyncio.run(llm.get_completion(messages=msgs_copy))

    # Update the chat w/ the response (and persist to the DB)
    messages.append({
        'role': 'assistant',
        'content': response_txt,
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
    return redirect(url_for("tutors.chat_interface", chat_id=chat_id))
