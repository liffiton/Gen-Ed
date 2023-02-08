import json
import markdown
import openai

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from . import prompts
from .db import get_db
from .auth import get_session_auth, login_required, class_config_required


def get_query(query_id):
    db = get_db()
    auth = get_session_auth()

    query_row = None
    response_html = None

    if auth['is_admin']:
        cur = db.execute("SELECT queries.*, users.username FROM queries JOIN users ON queries.user_id=users.id WHERE queries.id=?", [query_id])
    elif auth['role'] is not None and auth['role']['role'] == 'instructor':
        cur = db.execute("SELECT queries.*, users.username FROM queries JOIN users ON queries.user_id=users.id JOIN roles ON queries.role_id=roles.id WHERE roles.class_id=? AND queries.id=?", [auth['role']['class_id'], query_id])
    else:
        cur = db.execute("SELECT queries.*, users.username FROM queries JOIN users ON queries.user_id=users.id WHERE queries.user_id=? AND queries.id=?", [auth['user_id'], query_id])
    query_row = cur.fetchone()

    if query_row:
        if query_row['response_text']:
            response_html = markdown.markdown(
                query_row['response_text'],
                output_format="html5",
                extensions=['fenced_code', 'sane_lists', 'smarty'],
            )
        else:
            response_html = "<i>No response -- an error occurred.  Please try again.</i>"
    else:
        flash("Invalid id.", "warning")

    return query_row, response_html


def get_history():
    '''Fetch current user's query history.'''
    db = get_db()
    auth = get_session_auth()

    cur = db.execute("SELECT * FROM queries WHERE queries.user_id=? ORDER BY query_time DESC LIMIT 10", [auth['user_id']])
    history = cur.fetchall()
    return history


bp = Blueprint('helper', __name__, url_prefix="/help", template_folder='templates')


@bp.route("/")
@bp.route("/<int:query_id>")
@login_required
@class_config_required
def help_form(query_id=None):
    db = get_db()
    auth = get_session_auth()

    # default to most recently submitted language, if available, else the default language for the current class, if available
    selected_lang = None
    lang_row = db.execute("SELECT language FROM queries WHERE queries.user_id=? ORDER BY query_time DESC LIMIT 1", [auth['user_id']]).fetchone()
    if lang_row:
        selected_lang = lang_row['language']
    elif auth['role'] is not None:
        config_row = db.execute("SELECT config FROM classes WHERE id=?", [auth['role']['class_id']]).fetchone()
        class_config = json.loads(config_row['config'])
        selected_lang = class_config['default_lang']

    query_row = None

    # populate with a query+response if one is specified in the query string
    if query_id is not None:
        query_row, _ = get_query(query_id)   # _ because we don't need response_html here
        selected_lang = query_row['language']

    history = get_history()

    return render_template("help_form.html", query=query_row, history=history, selected_lang=selected_lang)


@bp.route("/view/<int:query_id>")
@login_required
@class_config_required
def help_view(query_id):
    query_row, response_html = get_query(query_id)
    history = get_history()

    return render_template("help_view.html", query=query_row, response_html=response_html, history=history)


def get_completion(prompt, stop_seq=None):
    openai.api_key = current_app.config["OPENAI_API_KEY"]
    try:
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
            response_txt += "\n\n[error: maximum length exceeded]"

    except openai.error.APIError as e:
        response = str(e)
        response_txt = "Error (APIError).  Something went wrong on our side.  Please try again, and if it repeats, let me know at mliffito@iwu.edu."
        pass
    except openai.error.Timeout as e:
        response = str(e)
        response_txt = "Error (Timeout).  Something went wrong on our side.  Please try again, and if it repeats, let me know at mliffito@iwu.edu."
        pass
    except openai.error.ServiceUnavailableError as e:
        response = str(e)
        response_txt = "Error (ServiceUnavailableError).  Something went wrong on our side.  Please try again, and if it repeats, let me know at mliffito@iwu.edu."
        pass
    except openai.error.RateLimitError as e:
        response = str(e)
        response_txt = "Error (RateLimitError).  The system is receiving too many requests right now.  Please try again in one minute.  If it does not resolve, please let me know at mliffito@iwu.edu."
        pass
    except Exception as e:
        response = str(e)
        response_txt = "Error (Exception).  Something went wrong on our side.  Please try again, and if it repeats, let me know at mliffito@iwu.edu."
        pass

    return response, response_txt


def run_query(language, code, error, issue):
    query_id = record_query(language, code, error, issue)

    db = get_db()
    auth = get_session_auth()
    class_id = auth['role']['class_id']
    class_row = db.execute("SELECT * FROM classes WHERE id=?", [class_id]).fetchone()
    class_config = json.loads(class_row['config'])
    avoid_set = set(x.strip() for x in class_config.get('avoid', '').split('\n') if x.strip() != '')

    prompt, stop_seq = prompts.make_main_prompt(language, code, error, issue, avoid_set)
    # TODO: store prompt template in database for internal reference, esp. if it changes over time
    #       (could just automatically add to a table if not present and get the autoID for it as foreign key)

    # short circuit for testing w/o using GPT credits
    if issue == "test":
        current_app.logger.info(prompt)
        record_response(query_id, "test response", "test response")
        return query_id

    response, response_txt = get_completion(prompt, stop_seq)

    if "```" in response_txt or "should look like" in response_txt or "should look something like" in response_txt:
        # That's probably too much code.  Let's clean it up...
        cleanup_prompt = prompts.make_cleanup_prompt(language, code, error, issue, orig_response_txt=response_txt)
        _, response_txt = get_completion(cleanup_prompt, stop_seq=None)

    record_response(query_id, response, response_txt)

    return query_id


def record_query(language, code, error, issue):
    db = get_db()
    auth = get_session_auth()
    role_id = auth['role']['id'] if auth['role'] else None

    cur = db.execute(
        "INSERT INTO queries (language, code, error, issue, user_id, role_id) VALUES (?, ?, ?, ?, ?, ?)",
        [language, code, error, issue, auth['user_id'], role_id]
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
@class_config_required
def help_request():
    lang_id = int(request.form["lang_id"])
    language = current_app.config["LANGUAGES"][lang_id]
    code = request.form["code"]
    error = request.form["error"]
    issue = request.form["issue"]

    # TODO: limit length of code/error/issue

    query_id = run_query(language, code, error, issue)

    return redirect(url_for(".help_view", query_id=query_id))
