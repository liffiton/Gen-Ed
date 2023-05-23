import asyncio
import json

from flask import Blueprint, flash, redirect, render_template, request, url_for

from plum.db import get_db
from plum.auth import get_session_auth, login_required
from plum.admin import bp as bp_admin, register_admin_page
from plum.openai import get_openai_key, get_completion
from plum.queries import get_query


bp = Blueprint('tutor', __name__, url_prefix="/tutor", template_folder='templates')


@bp.route("/")
@login_required
def tutor_form(chat_id=None):
    return render_template("tutor_new_form.html")


@bp.route("/chat/create", methods=["POST"])
@login_required
def start_chat():
    auth = get_session_auth()
    user_id = auth['user_id']
    role_id = auth['lti']['role_id'] if auth['lti'] else None

    topic = request.form['topic']
    context = request.form.get('context', None)

    chat_id = create_chat(user_id, role_id, topic, context)

    run_chat_round(chat_id)

    return redirect(url_for("tutor.chat_interface", chat_id=chat_id))


@bp.route("/chat/create_from_query", methods=["POST"])
@login_required
def start_chat_from_query():
    auth = get_session_auth()
    user_id = auth['user_id']
    role_id = auth['lti']['role_id'] if auth['lti'] else None

    query_id = request.form['query_id']
    topic = request.form['topic']

    # build context from the specified query
    query_row, response = get_query(query_id)
    context = f"""\
The user is working with the {query_row['language']} language.
"""

    chat_id = create_chat(user_id, role_id, topic, context)

    run_chat_round(chat_id)

    return redirect(url_for("tutor.chat_interface", chat_id=chat_id))


@bp.route("/chat/<int:chat_id>")
@login_required
def chat_interface(chat_id):
    #auth = get_session_auth()
    #user_id = auth['user_id']
    #role_id = auth['lti']['role_id'] if auth['lti'] else None

    # TODO: auth/ownership checks
    chat, topic, context = get_chat(chat_id)

    if chat is None:
        flash("Invalid id", "warning")
        return render_template("error.html")

    return render_template("tutor_view.html", chat_id=chat_id, topic=topic, context=context, chat=chat)


def create_chat(user_id, role_id, topic, context=None):
    db = get_db()
    cur = db.execute(
        "INSERT INTO tutor_chats (user_id, role_id, topic, context, chat_json) VALUES (?, ?, ?, ?, ?)",
        [user_id, role_id, topic, context, json.dumps([])]
    )
    new_row_id = cur.lastrowid
    db.commit()
    return new_row_id


def get_chat(chat_id):
    # TODO: auth/ownership checks
    db = get_db()
    chat_row = db.execute(
        "SELECT chat_json, topic, context FROM tutor_chats WHERE id=?",
        [chat_id]
    ).fetchone()

    if not chat_row:
        return None, None

    chat_json = chat_row['chat_json']
    chat = json.loads(chat_json)
    topic = chat_row['topic']
    context = chat_row['context']

    return chat, topic, context


def get_response(chat):
    ''' Get a new 'assistant' completion for the specified chat.

    Parameters:
      - chat: A list of dicts, each containing a message with 'role' and 'content' keys,
              following the OpenAI chat completion API spec.

    Returns a tuple containing:
      1) A response object from the OpenAI completion (to be stored in the database).
      2) The response text.
    '''
    # get openai API key for following completion
    api_key = get_openai_key()
    if not isinstance(api_key, str) or api_key == '':
        msg = "Error: API key not set.  Request cannot be submitted."
        return msg, msg

    response, text = asyncio.run(get_completion(
        api_key,
        messages=chat,
        model='turbo',
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


def run_chat_round(chat_id, message=None):
    # Get the specified chat
    chat, topic, context = get_chat(chat_id)

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

I don't want you to just tell me how something works directly, but rather start by asking me about what I do know and prompting me from there to help me develop my understanding.

I will not understand a lot of detail at once, so I need you to carefully add a small amount of understanding at a time.

Check to see how well I've understood each piece. If you just ask me if I understand, I will say yes even if I don't, so please NEVER ask if I understand something. Instead of asking "does that make sense?", always check my understanding by asking me a question that makes me demonstrate understanding. If and only if I can apply the knowledge correctly, then move on to the next piece of information.
"""
    context_msg = f"I have this additional context about teaching the user this topic:\n\n{context}"
    monologue = """[Internal monologue] I am a Socratic tutor. I am trying to help the user learn a topic by leading them to understanding, not by telling them things directly.  I should check to see how well the user understands each aspect of what I am teaching. If I just ask them if they understand, they will say yes even if they don't, so I should NEVER ask if they understand something. Instead of asking "does that make sense?", I need to check their understanding by asking them a question that makes them demonstrate understanding. If and only if they can apply the knowledge correctly, then I should move on to the next piece of information."""

    expanded_chat = [
        {'role': 'user', 'content': topic},
        {'role': 'user', 'content': opening_msg},
        {'role': 'assistant', 'content': context_msg},
        *chat,  # chat is a list; expand it here with *
        {'role': 'assistant', 'content': monologue},
    ]

    response_obj, response_txt = get_response(expanded_chat)

    # Update the chat w/ the response
    chat.append({
        'role': 'assistant',
        'content': response_txt,
    })
    save_chat(chat_id, chat)

    return chat, response_txt


@bp.route("/message", methods=["POST"])
@login_required
def new_message():
    chat_id = request.form["id"]
    new_msg = request.form["message"]

    # TODO: limit length

    # Run a round of the chat with the given message.
    chat, response_txt = run_chat_round(chat_id, new_msg)

    # Send the user back to the now-updated chat view
    return redirect(url_for("tutor.chat_interface", chat_id=chat_id))


# ### Admin routes ###

@register_admin_page("Tutor Chats")
@bp_admin.route("/tutor/")
@bp_admin.route("/tutor/<int:id>")
def tutor_admin(id=None):
    db = get_db()
    chats = db.execute("""
        SELECT
            tutor_chats.id,
            users.username,
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
    """).fetchall()

    if id is not None:
        chat_row = db.execute("SELECT users.username, topic, chat_json FROM tutor_chats JOIN users ON tutor_chats.user_id=users.id WHERE tutor_chats.id=?", [id]).fetchone()
        chat = json.loads(chat_row['chat_json'])
    else:
        chat_row = None
        chat = None

    return render_template("tutor_admin.html", chats=chats, chat_row=chat_row, chat=chat)
