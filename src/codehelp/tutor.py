# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import json

from flask import Blueprint, flash, redirect, render_template, request, url_for

from plum.db import get_db
from plum.auth import get_auth, login_required, tester_required
from plum.admin import bp as bp_admin, register_admin_link
from plum.openai import with_llm, get_completion
from plum.queries import get_query


bp = Blueprint('tutor', __name__, url_prefix="/tutor", template_folder='templates')


@bp.before_request
@tester_required
@login_required
def before_request():
    """Apply decorators to protect all tutor blueprint endpoints.
    Use @tester_required first so that non-logged-in users get a 404 as well.
    """
    pass


@bp.route("/")
def tutor_form():
    chat_history = get_chat_history()
    return render_template("tutor_new_form.html", chat_history=chat_history)


@bp.route("/chat/create", methods=["POST"])
@with_llm()
def start_chat(llm_dict):
    topic = request.form['topic']
    context = request.form.get('context', None)

    chat_id = create_chat(topic, context)

    run_chat_round(llm_dict, chat_id)

    return redirect(url_for("tutor.chat_interface", chat_id=chat_id))


@bp.route("/chat/create_from_query", methods=["POST"])
@with_llm()
def start_chat_from_query(llm_dict):
    topic = request.form['topic']

    # build context from the specified query
    query_id = request.form['query_id']
    query_row, response = get_query(query_id)
    context = f"The user is working with the {query_row['language']} language."

    chat_id = create_chat(topic, context)

    run_chat_round(llm_dict, chat_id)

    return redirect(url_for("tutor.chat_interface", chat_id=chat_id))


@bp.route("/chat/<int:chat_id>")
def chat_interface(chat_id):
    chat, topic, context = get_chat(chat_id)

    if chat is None:
        flash("Invalid id.", "warning")
        return render_template("error.html")

    chat_history = get_chat_history()

    return render_template("tutor_view.html", chat_id=chat_id, topic=topic, context=context, chat=chat, chat_history=chat_history)


def create_chat(topic, context=None):
    auth = get_auth()
    user_id = auth['user_id']
    role_id = auth['role_id']

    db = get_db()
    cur = db.execute(
        "INSERT INTO tutor_chats (user_id, role_id, topic, context, chat_json) VALUES (?, ?, ?, ?, ?)",
        [user_id, role_id, topic, context, json.dumps([])]
    )
    new_row_id = cur.lastrowid
    db.commit()
    return new_row_id


def get_chat_history(limit=10):
    '''Fetch current user's chat history.'''
    db = get_db()
    auth = get_auth()

    history = db.execute("SELECT * FROM tutor_chats WHERE user_id=? ORDER BY id DESC LIMIT ?", [auth['user_id'], limit]).fetchall()
    return history


def get_chat(chat_id):
    db = get_db()
    auth = get_auth()

    chat_row = db.execute(
        "SELECT chat_json, topic, context, tutor_chats.user_id, roles.class_id "
        "FROM tutor_chats "
        "JOIN users ON tutor_chats.user_id=users.id "
        "LEFT JOIN roles ON tutor_chats.role_id=roles.id "
        "WHERE tutor_chats.id=?",
        [chat_id]
    ).fetchone()

    if not chat_row:
        return None, None, None

    access_allowed = \
        (auth['user_id'] == chat_row['user_id']) \
        or auth['is_admin'] \
        or (auth['role'] == 'instructor' and auth['class_id'] == chat_row['class_id'])

    if not access_allowed:
        return None, None, None

    chat_json = chat_row['chat_json']
    chat = json.loads(chat_json)
    topic = chat_row['topic']
    context = chat_row['context']

    return chat, topic, context


def get_response(llm_dict, chat):
    ''' Get a new 'assistant' completion for the specified chat.

    Parameters:
      - chat: A list of dicts, each containing a message with 'role' and 'content' keys,
              following the OpenAI chat completion API spec.

    Returns a tuple containing:
      1) A response object from the OpenAI completion (to be stored in the database).
      2) The response text.
    '''
    response, text = asyncio.run(get_completion(
        api_key=llm_dict['key'],
        messages=chat,
        model=llm_dict['model'],
        n=1,
    ))

    return response, text


def save_chat(chat_id, chat):
    db = get_db()
    db.execute(
        "UPDATE tutor_chats SET chat_json=? WHERE id=?",
        [json.dumps(chat), chat_id]
    )
    db.commit()


def run_chat_round(llm_dict, chat_id, message=None):
    # Get the specified chat
    chat, topic, context = get_chat(chat_id)

    if chat is None:
        # No access.
        return

    # Add the given message(s) to the chat
    if message is not None:
        chat.append({
            'role': 'user',
            'content': message,
        })

    save_chat(chat_id, chat)

    # Get a response (completion) from the API using an expanded version of the chat messages
    # Insert an opening "from" the user and an internal monologue to guide the assistant before generating it's actual response
    opening_msg = """\
You are a Socratic tutor for helping me learn about a computer science topic.  The topic is given in the previous message.

If the topic is broad and it could take more than one chat session to cover all aspects of it, please ask me to clarify what, specifically, I'm attempting to learn about it.

I will not understand a lot of detail at once, so I need you to carefully add a small amount at a time.  I don't want you to just tell me how something works directly, but rather start by asking me about what I do know and prompting me from there to help me develop my understanding.  Before moving on, always ask me to answer a question or solve a problem with these characteristics:
 - Answering correctly requires understanding the current topic well.
 - The answer is not found in what you have told me.
 - I can reasonably be expected to answer correctly given what I seem to know so far.
"""
    context_msg = f"I have this additional context about teaching the user this topic:\n\n{context}"
    monologue = """[Internal monologue] I am a Socratic tutor. I am trying to help the user learn a topic by leading them to understanding, not by telling them things directly.  I should check to see how well the user understands each aspect of what I am teaching. But if I just ask them if they understand, they will say yes even if they don't, so I should NEVER ask if they understand something. Instead of asking "does that make sense?", I need to check their understanding by asking them a question that makes them demonstrate understanding. It should be a question for which they can only answer correctly if they understand the concept, and it should not be a question I've already given an answer for myself.  If and only if they can apply the knowledge correctly, then I should move on to the next piece of information.

I can use Markdown formatting in my responses."""

    expanded_chat = [
        {'role': 'user', 'content': topic},
        {'role': 'user', 'content': opening_msg},
    ] + ([{'role': 'assistant', 'content': context_msg}] if context else []) + [
        *chat,  # chat is a list; expand it here with *
        {'role': 'assistant', 'content': monologue},
    ]

    response_obj, response_txt = get_response(llm_dict, expanded_chat)

    # Update the chat w/ the response
    chat.append({
        'role': 'assistant',
        'content': response_txt,
    })
    save_chat(chat_id, chat)


@bp.route("/message", methods=["POST"])
@with_llm()
def new_message(llm_dict):
    chat_id = request.form["id"]
    new_msg = request.form["message"]

    # TODO: limit length

    # Run a round of the chat with the given message.
    run_chat_round(llm_dict, chat_id, new_msg)

    # Send the user back to the now-updated chat view
    return redirect(url_for("tutor.chat_interface", chat_id=chat_id))


# ### Admin routes ###

@register_admin_link("Tutor Chats")
@bp_admin.route("/tutor/")
@bp_admin.route("/tutor/<int:id>")
def tutor_admin(id=None):
    db = get_db()
    chats = db.execute("""
        SELECT
            tutor_chats.id,
            users.display_name,
            tutor_chats.topic,
            (
                SELECT
                    COUNT(*)
                FROM
                    json_each(tutor_chats.chat_json)
                WHERE
                    json_extract(json_each.value, '$.role')='user'
            ) as user_msgs
        FROM
            tutor_chats
        JOIN
            users ON tutor_chats.user_id=users.id
        ORDER BY
            tutor_chats.id DESC
    """).fetchall()

    if id is not None:
        chat_row = db.execute("SELECT users.display_name, topic, chat_json FROM tutor_chats JOIN users ON tutor_chats.user_id=users.id WHERE tutor_chats.id=?", [id]).fetchone()
        chat = json.loads(chat_row['chat_json'])
    else:
        chat_row = None
        chat = None

    return render_template("tutor_admin.html", chats=chats, chat_row=chat_row, chat=chat)
