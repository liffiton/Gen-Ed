# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
from collections.abc import AsyncGenerator, Iterator

import msgspec
from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    stream_with_context,
    url_for,
)
from werkzeug.wrappers.response import Response

from components.code_contexts import (
    ContextConfig,
    contexts_config_table,
)
from gened.access import (
    Access,
    RequireComponent,
    check_access,
    class_enabled_required,
    route_requires,
)
from gened.app_data import DataAccessError
from gened.auth import get_auth
from gened.classes import switch_class
from gened.db import get_db
from gened.llm import LLM, ChatMessage, with_llm

from . import prompts
from .data import ChatData, ChatMode, GuidedAnalysis, chats_data_source
from .guided import guided_tutor_config_table

bp = Blueprint('tutors', __name__, url_prefix='/tutor', template_folder='templates')

# NOTE: Blueprint default access controls set in __init__ via availability_requirements


@bp.route("/new")
@bp.route("/new/<int:class_id>")
def new_chat_form(class_id: int | None = None) -> Response | str:
    auth = get_auth()

    if class_id is not None:
        success = switch_class(class_id)
        if not success:
            current_app.logger.warning(f"User {auth.user_id} failed to switch to class {class_id}.")
            # Can't access the specified class
            flash("Cannot access specified class.  Make sure you are logged in correctly before using this link.", "danger")
            return make_response(render_template("error.html"), 400)

        contexts = None
        tutors = None

        if 'ctx_name' in request.args:
            ctx_name = request.args['ctx_name']
            context = contexts_config_table.get_item_by_name(ctx_name)
            if not context:
                flash(f"Context not found: '{ctx_name}'", "danger")
                return make_response(render_template("error.html"), 400)
            contexts = {context.name: context.desc_html()}
        elif 'tutor_name' in request.args:
            tutor_name = request.args['tutor_name']
            tutor = guided_tutor_config_table.get_item_by_name(tutor_name)
            if not tutor:
                flash(f"Tutor not found: '{tutor_name}'", "danger")
                return make_response(render_template("error.html"), 400)
            tutors = [tutor]
        else:
            return make_response(render_template("error.html"), 400)

    else:
        # All contexts and all guided tutors
        contexts_list = contexts_config_table.get_items(available_only=True)
        # turn into format we can pass to js via JSON
        contexts = {ctx.name: ctx.desc_html() for ctx in contexts_list}

        # Get all pre-defined guided tutors that are available:
        #   current date anywhere on earth (using UTC+12) is at or after the saved date
        tutors = guided_tutor_config_table.get_items(available_only=True)

    # check if each feature is enabled
    if not check_access(RequireComponent("tutors", "inquiry")):
        contexts = None  # don't display the form
    if not check_access(RequireComponent("tutors", "guided")):
        tutors = None  # don't display the form

    recent_chats = chats_data_source.get_user_data(limit=10)

    return render_template("tutor_new_form.html", contexts=contexts, tutors=tutors, recent_chats=recent_chats)


@bp.route("/create_inquiry", methods=["POST"])
@route_requires(Access.CLASS_ENABLED, RequireComponent("tutors", feature="inquiry"))
@with_llm(spend_token=True)
def create_inquiry_chat(llm: LLM) -> Response:
    topic = request.form['topic']
    context: ContextConfig | None = None

    if context_name := request.form.get('context'):
        context = contexts_config_table.get_item_by_name(context_name)
        if context is None:
            flash(f"Context not found: {context_name}", "danger")
            return make_response(render_template("error.html"), 400)

    context_name = context.name if context else None
    context_string = context.prompt_str() if context else None
    auth = get_auth()
    tikz_enabled = 'tikz_experiment' in auth.class_experiments
    sys_prompt = prompts.inquiry_sys_msg_tpl.render(topic=topic, context=context_string, tikz_enabled=tikz_enabled)

    chat = _create_chat(topic, context_name, sys_prompt, "inquiry")

    try:
        run_chat_round(llm, chat)
    except RuntimeError as e:
        current_app.logger.error(f"Error running inquiry chat round: {e}")
        # On error, erase the nascent chat and tell the user what happened.
        erase_chat(chat)
        flash(str(e), 'danger')
        return make_response(render_template("error.html"), 502)

    return redirect(url_for("tutors.chat_interface", chat_id=chat.id))


@bp.route("/create_guided", methods=["POST"])
@route_requires(Access.CLASS_ENABLED, RequireComponent("tutors", feature="guided"))
@with_llm(spend_token=True)
def create_guided_chat(llm: LLM) -> Response:
    auth = get_auth()
    assert auth.cur_class is not None

    tutor_id = request.form['tutor_id']
    tutor_config = guided_tutor_config_table.get_item_by_id(int(tutor_id))

    if tutor_config is None:
        flash("Tutor not found.", "danger")
        return make_response(render_template("error.html"), 400)

    # Get documents marked for use in chat
    chat_docs = [doc for doc in tutor_config.documents if 'chat' in doc.use_in]

    tikz_enabled = 'tikz_experiment' in auth.class_experiments
    sys_prompt = prompts.guided_sys_msg_tpl.render(tutor_config=tutor_config, documents=chat_docs, tikz_enabled=tikz_enabled)

   chat = _create_chat(tutor_config.topic, context_name=None, sys_prompt=sys_prompt, mode="guided")

    if tutor_config.opening_message:
        # Use the pre-generated/instructor-written opening message — no LLM call needed.
        chat.messages.append({
            'role': 'assistant',
            'content': tutor_config.opening_message,
        })
        save_chat(chat)
    else:
        # Fallback: no saved opening message, generate one live (old behavior).
        try:
            run_chat_round(llm, chat)
        except RuntimeError as e:
            current_app.logger.error(f"Error running guided chat round: {e}")
            erase_chat(chat)
            flash(str(e), 'danger')
            return make_response(render_template("error.html"), 502)

    return redirect(url_for("tutors.chat_interface", chat_id=chat.id))

def _create_chat(topic: str, context_name: str | None, sys_prompt: str, mode: ChatMode) -> ChatData:
    db = get_db()
    auth = get_auth()
    user_id = auth.user_id
    class_id = auth.cur_class.class_id if auth.cur_class else None
    role_id = auth.cur_class.role_id if auth.cur_class else None

    chat_data = ChatData(
        user_id=user_id,
        class_id=class_id,
        topic=topic,
        context_name=context_name,
        messages=[{"role": "system", "content": sys_prompt}],
        usages=[],
        mode=mode,
    )

    cur = db.execute(
        "INSERT INTO chats (user_id, role_id, chat_json) VALUES (?, ?, ?)",
        [user_id, role_id, msgspec.json.encode(chat_data).decode()]
    )
    new_row_id = cur.lastrowid

    db.commit()

    assert new_row_id is not None
    return msgspec.structs.replace(chat_data, id=new_row_id)


@bp.route("/<int:chat_id>")
def chat_interface(chat_id: int) -> str | Response:
    try:
        chat_data = get_chat(chat_id)
    except DataAccessError:
        abort(400, "Invalid id.")

    recent_chats = chats_data_source.get_user_data(limit=10)

    auth = get_auth()
    assert auth.user
    is_owner = auth.user.id == chat_data.user_id
    is_current_class = auth.cur_class is not None and auth.cur_class.class_id == chat_data.class_id
    show_message_input = is_owner and is_current_class

    return render_template("tutor_view.html", chat=chat_data, recent_chats=recent_chats, msg_input=show_message_input)


def get_chat(chat_id: int) -> ChatData:
    chat_row = chats_data_source.get_row(chat_id)

    chat_json = chat_row['chat_json']

    chat_data = msgspec.json.decode(chat_json, type=ChatData)

    return msgspec.structs.replace(
        chat_data,
        id=chat_id,
        user_id=chat_row['user_id'],
        user_json=chat_row['user'],
        class_id=chat_row['class_id']
    )


def save_chat(chat_data: ChatData) -> None:
    # remove redundant items (already stored elsewhere in db)
    # the Struct's omit_default=True will keep them from being encoded
    filtered = msgspec.structs.replace(
        chat_data,
        id=None,
        user_id=None,
        user_json=None,
        class_id=None
    )

    db = get_db()
    db.execute(
        "UPDATE chats SET chat_json=? WHERE id=?",
        [msgspec.json.encode(filtered).decode(), chat_data.id]
    )
    db.commit()


def erase_chat(chat_data: ChatData) -> None:
    db = get_db()
    db.execute("DELETE FROM chats WHERE id=?", [chat_data.id])
    db.commit()


def run_chat_round(llm: LLM, chat: ChatData) -> None:
    """ Run a single round of the given chat with the given LLM.

    Uses stream_chat_round and simply consumes all of its yielded outputs,
    relying on its side-effects (updating the chat in the database).
    """
    async def consume_stream_chat() -> None:
        async for _ in stream_chat_round(llm, chat):
            pass
    asyncio.run(consume_stream_chat())


async def stream_chat_round(llm: LLM, chat: ChatData) -> AsyncGenerator[str, None]:
    """ Run a single round of the given chat with the given LLM, streaming
    response chunks and potentially conversation analysis via yield.
    """
    msgs = chat.openai_messages[:]

    if len(msgs) == 0 or (len(msgs) == 1 and msgs[0]['role'] == 'system'):
        # Gemini, at least, requires a user message to start, but we don't need
        # to save or display it, so only add this to the copy of the messages
        # rather than updating the messages in the `chat` object.
        msgs.append({
            'role': 'user',
            'content': 'Please generate an initial message for the user.',
        })

    # Generate a completion and stream the response
    stream = await llm.stream_completion(messages=msgs)

    response_txt = ""
    async for chunk in stream:
        if chunk.choices:
            choice = chunk.choices[0]
            delta = choice.delta.content or ""

            if choice.finish_reason == "length":  # "length" if max_completion_tokens reached
                delta += "\n\n[error: maximum length exceeded]"

            yield delta
            response_txt += delta
        elif chunk.usage is not None:
            # usage available in the final chunk
            chat.usages.append(chunk.usage.model_dump())

    # Update the chat w/ the response (and persist to the DB)
    chat.messages.append({
        'role': 'assistant',
        'content': response_txt,
    })
    save_chat(chat)

    if chat.mode == "guided":
        # Summarize/analyze the chat so far
        await _analyze_guided_chat(chat, llm)


async def _analyze_guided_chat(chat_data: ChatData, llm: LLM) -> ChatData:
    analyze_messages: list[ChatMessage] = [
        *chat_data.openai_messages,
        {'role': 'user', 'content': prompts.guided_analyze_tpl.render(chat=chat_data)},
    ]
    _analyze_response, analyze_response_txt = await llm.get_completion(
        messages=analyze_messages,
        extra_args={
            'response_format': {'type': 'json_object'},
        },
    )
    try:
        analysis = msgspec.json.decode(analyze_response_txt, type=GuidedAnalysis)
    except msgspec.DecodeError:
        current_app.logger.warning(f"Invalid JSON response in _analyze_guided_chat: {analyze_response_txt}")
    else:
        chat_data.analysis = analysis
        save_chat(chat_data)

    return chat_data


@bp.route("/progress/<int:chat_id>")
def get_progress(chat_id: int) -> str:
    try:
        chat_data = get_chat(chat_id)
    except DataAccessError:
        abort(400, "Invalid id.")

    return render_template("progress_widget.html", chat=chat_data)


@bp.route("/post_message.sse", methods=["POST"])  # '.sse' extension needed for reverse proxy config to disable buffering / allow streaming
@class_enabled_required
@with_llm(spend_token=True)
def new_message(llm: LLM) -> Response:
    chat_id = int(request.form["id"])
    new_msg = request.form["message"]

    # TODO: limit length

    # Get the specified chat
    try:
        chat = get_chat(chat_id)
    except DataAccessError:
        abort(400, "Invalid id")

    messages = chat.messages

    # Add the new message to the chat (persisting to the DB)
    messages.append({
        'role': 'user',
        'content': new_msg,
    })

    # Stream back a response (while "translating" the async generator into a sync generator)
    async_stream = stream_chat_round(llm, chat)

    runner = asyncio.Runner()
    try:
        # Get first chunk before we send a Response so we can catch errors
        # and abort first if needed.
        first_chunk = runner.run(anext(async_stream))
    except RuntimeError as e:
        current_app.logger.error(f"Error getting chat response: {e}")
        return Response(str(e), 502, mimetype='text/plain')

    # only save the user's new message if the response succeeds
    # (front-end can let the user re-submit it if they want)
    save_chat(chat)

    def stream_response() -> Iterator[str]:
        yield first_chunk
        while True:
            try:
                chunk: str = runner.run(anext(async_stream))
                yield chunk
            except StopAsyncIteration:
                break
        runner.close()

    return Response(
        stream_with_context(stream_response()),
        mimetype="text/event-stream",
    )
