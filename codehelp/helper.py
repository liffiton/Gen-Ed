import asyncio
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
    elif auth['lti'] is not None and auth['lti']['role'] == 'instructor':
        cur = db.execute("SELECT queries.*, users.username FROM queries JOIN users ON queries.user_id=users.id JOIN roles ON queries.role_id=roles.id WHERE (roles.class_id=? OR queries.user_id=?) AND queries.id=?", [auth['lti']['class_id'], auth['user_id'], query_id])
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
    elif auth['lti'] is not None:
        config_row = db.execute("SELECT config FROM classes WHERE id=?", [auth['lti']['class_id']]).fetchone()
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


def get_openai_key():
    '''Get the openai API key for the current consumer,
       or else use the default key in the config for non-LTI users.'''
    db = get_db()
    auth = get_session_auth()
    if auth['lti'] is None:
        # default key for non-LTI users
        return current_app.config["OPENAI_API_KEY"]
    else:
        consumer_row = db.execute("SELECT openai_key FROM consumers WHERE lti_consumer=?", [auth['lti']['consumer']]).fetchone()
        return consumer_row['openai_key']


async def get_completion(prompt, stop_seq=None):
    try:
        response = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
        #response = await openai.Completion.acreate(
        #    model="text-davinci-003",
        #    prompt=prompt,
            temperature=0.25,
            max_tokens=1000,
            stop=stop_seq,
            # TODO: add user= parameter w/ unique ID of user (e.g., hash of username+email or similar)
        )

        response_txt = response.choices[0].message["content"]
        #response_txt = response.choices[0].text
        response_reason = response.choices[0].finish_reason  # e.g. "length" if max_tokens reached

        if response_reason == "length":
            response_txt += "\n\n[error: maximum length exceeded]"

    except openai.error.APIError as e:
        current_app.logger.error(e)
        response = str(e)
        response_txt = "Error (APIError).  Something went wrong on our side.  Please try again, and if it repeats, let me know at mliffito@iwu.edu."
        pass
    except openai.error.Timeout as e:
        current_app.logger.error(e)
        response = str(e)
        response_txt = "Error (Timeout).  Something went wrong on our side.  Please try again, and if it repeats, let me know at mliffito@iwu.edu."
        pass
    except openai.error.ServiceUnavailableError as e:
        current_app.logger.error(e)
        response = str(e)
        response_txt = "Error (ServiceUnavailableError).  Something went wrong on our side.  Please try again, and if it repeats, let me know at mliffito@iwu.edu."
        pass
    except openai.error.RateLimitError as e:
        current_app.logger.error(e)
        response = str(e)
        response_txt = "Error (RateLimitError).  The system is receiving too many requests right now.  Please try again in one minute.  If it does not resolve, please let me know at mliffito@iwu.edu."
        pass
    except Exception as e:
        current_app.logger.error(e)
        response = str(e)
        response_txt = "Error (Exception).  Something went wrong on our side.  Please try again, and if it repeats, let me know at mliffito@iwu.edu."
        pass

    return response, response_txt.strip()


async def run_query_prompts(language, code, error, issue):
    db = get_db()
    auth = get_session_auth()

    # set openai API key for following completions
    api_key = get_openai_key()
    if not api_key:
        msg = "Error: API key not set.  Request cannot be submitted."
        return msg, msg
    openai.api_key = api_key

    # create "avoid set" from class configuration
    if auth['lti'] is not None:
        class_id = auth['lti']['class_id']
        class_row = db.execute("SELECT * FROM classes WHERE id=?", [class_id]).fetchone()
        class_config = json.loads(class_row['config'])
        avoid_set = set(x.strip() for x in class_config.get('avoid', '').split('\n') if x.strip() != '')
    else:
        avoid_set = set()

    # Launch the "sufficient detail" check concurrently with the main prompt to save time if it comes back as sufficient.
    task_sufficient = asyncio.create_task(
        get_completion(*prompts.make_sufficient_prompt(language, code, error, issue))
    )

    task_main = asyncio.create_task(
        get_completion(*prompts.make_main_prompt(language, code, error, issue, avoid_set))
    )

    # Store all responses received
    responses = []

    # Check whether there is sufficient information
    response_sufficient, response_sufficient_txt = await task_sufficient
    responses.append(response_sufficient)

    # And let's get the main response.
    response, response_txt = await task_main
    responses.append(response)

    if "```" in response_txt or "should look like" in response_txt or "should look something like" in response_txt:
        # That's probably too much code.  Let's clean it up...
        cleanup_prompt = prompts.make_cleanup_prompt(orig_response_txt=response_txt)
        cleanup_response, cleanup_response_txt = await get_completion(cleanup_prompt, stop_seq=None)
        responses.append(cleanup_response)
        response_txt = cleanup_response_txt

    if response_sufficient_txt.endswith("OK") or response_sufficient_txt.endswith("OK."):
        # We're using just the main response.
        return responses, response_txt
    else:
        # Give them the request for more information plus the main response, in case it's helpful.
        final_txt = f"{response_sufficient_txt}\n\n*[However, here's an attempt at helping anyway:]*\n\n{response_txt}"
        return responses, final_txt


def run_query(language, code, error, issue):
    query_id = record_query(language, code, error, issue)

    responses, final_txt = asyncio.run(run_query_prompts(language, code, error, issue))

    record_response(query_id, responses, final_txt)

    return query_id


def record_query(language, code, error, issue):
    db = get_db()
    auth = get_session_auth()
    role_id = auth['lti']['role_id'] if auth['lti'] else None

    cur = db.execute(
        "INSERT INTO queries (language, code, error, issue, user_id, role_id) VALUES (?, ?, ?, ?, ?, ?)",
        [language, code, error, issue, auth['user_id'], role_id]
    )
    new_row_id = cur.lastrowid
    db.commit()

    return new_row_id


def record_response(query_id, responses, final_txt):
    db = get_db()

    db.execute(
        "UPDATE queries SET response_json=?, response_text=? WHERE id=?",
        [json.dumps(responses), final_txt, query_id]
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


@bp.route("/post_helpful", methods=["POST"])
@login_required
def post_helpful():
    db = get_db()
    auth = get_session_auth()

    query_id = int(request.form['id'])
    value = int(request.form['value'])
    db.execute("UPDATE queries SET helpful=? WHERE id=? AND user_id=?", [value, query_id, auth['user_id']])
    db.commit()
    return ""
