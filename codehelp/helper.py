import json
import markdown
import openai

from flask import Blueprint, current_app, redirect, render_template, request, session, url_for

from . import prompts
from .db import get_db
from .auth import KEY_AUTH_USERID, KEY_AUTH_ROLE, login_required


bp = Blueprint('helper', __name__, url_prefix="/help", template_folder='templates')


@bp.route("/")
@bp.route("/<int:query_id>")
@login_required
def help_form(query_id=None):
    db = get_db()

    query_row = None
    response_html = None
    selected_lang = None

    # default to most recently submitted language, if available (overridden if viewing a result)
    lang_row = db.execute("SELECT language FROM queries WHere queries.user_id=? ORDER BY query_time DESC LIMIT 1", [session[KEY_AUTH_USERID]]).fetchone()
    if lang_row:
        selected_lang = lang_row['language']

    # populate with a query+response if one is specified in the query string
    if query_id is not None:
        if session[KEY_AUTH_ROLE] == "admin":
            cur = db.execute("SELECT * FROM queries WHERE queries.id=?", [query_id])
        else:
            cur = db.execute("SELECT * FROM queries WHERE queries.user_id=? AND queries.id=?", [session[KEY_AUTH_USERID], query_id])
        query_row = cur.fetchone()
        if query_row:
            selected_lang = query_row['language']
            response_html = markdown.markdown(
                query_row['response_text'],
                output_format="html5",
                extensions=['fenced_code', 'sane_lists', 'smarty'],
            )

    # fetch current user's query history
    cur = db.execute("SELECT * FROM queries WHERE queries.user_id=? ORDER BY query_time DESC LIMIT 10", [session[KEY_AUTH_USERID]])
    history = cur.fetchall()

    return render_template("help_form.html", query=query_row, response_html=response_html, history=history, languages=current_app.config["LANGUAGES"], selected_lang=selected_lang)


def run_query(language, code, error, issue):
    prompt, stop_seq = prompts.make_main_prompt(language, code, error, issue)

    # TODO: store prompt template in database for internal reference, esp. if it changes over time
    #       (could just automatically add to a table if not present and get the autoID for it as foreign key)

    query_id = record_query(language, code, error, issue)

    openai.api_key = current_app.config["OPENAI_API_KEY"]
    response = openai.Completion.create(
        model="text-davinci-003",
        prompt=prompt,
        temperature=0.25,
        max_tokens=1000,
        stop=stop_seq,
        # TODO: add user= parameter w/ unique ID of user (e.g., hash of username+email or similar)
    )

    response_txt = response.choices[0].text
    response_reason = response.choices[0].finish_reason  # e.g. "length" if max_tokens reached

    if response_reason == "length":
        response_txt += "\n[error: maximum length exceeded]"

    if "```" in response_txt:
        # That's probably too much code.  Let's clean it up...
        cleanup_prompt = prompts.make_cleanup_prompt(language, code, error, issue, orig_response_txt=response_txt)
        cleanup_response = openai.Completion.create(
            model="text-davinci-003",
            prompt=cleanup_prompt,
            temperature=0.25,
            max_tokens=1000,
            # TODO: add user= parameter w/ unique ID of user (e.g., hash of username+email or similar)
        )
        response_txt = cleanup_response.choices[0].text

    record_response(query_id, response, response_txt)

    return query_id


def record_query(language, code, error, issue):
    db = get_db()

    cur = db.execute(
        "INSERT INTO queries (language, code, error, issue, user_id) VALUES (?, ?, ?, ?, ?)",
        [language, code, error, issue, session[KEY_AUTH_USERID]]
    )
    new_row_id = cur.lastrowid
    db.commit()

    return new_row_id


def record_response(query_id, response, response_txt):
    db = get_db()

    db.execute(
        "UPDATE queries SET response_json=?, response_text=? WHERE id=?",
        [json.dumps(response), response_txt, query_id]
    )
    db.commit()


@bp.route("/request", methods=["POST"])
@login_required
def help_request():
    lang_id = int(request.form["lang_id"])
    language = current_app.config["LANGUAGES"][lang_id]
    code = request.form["code"]
    error = request.form["error"]
    issue = request.form["issue"]

    # TODO: limit length of code/error/issue

    query_id = run_query(language, code, error, issue)

    return redirect(url_for(".help_form", query_id=query_id))
