import asyncio
import json

from flask import Blueprint, current_app, redirect, render_template, request, url_for

from . import prompts
from plum.db import get_db
from plum.auth import get_session_auth, login_required, class_config_required, tester_required
from plum.openai import with_openai_key, get_completion
from plum.queries import get_query, get_history


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
    elif auth['class_id'] is not None:
        config_row = db.execute("SELECT config FROM classes WHERE id=?", [auth['class_id']]).fetchone()
        class_config = json.loads(config_row['config'])
        selected_lang = class_config['default_lang']

    query_row = None

    # populate with a query+response if one is specified in the query string
    if query_id is not None:
        query_row, _ = get_query(query_id)   # _ because we don't need responses here
        selected_lang = query_row['language']

    history = get_history()

    return render_template("help_form.html", query=query_row, history=history, selected_lang=selected_lang)


@bp.route("/view/<int:query_id>")
@login_required
def help_view(query_id):
    query_row, responses = get_query(query_id)
    history = get_history()
    if query_row and query_row['topics_json']:
        topics = json.loads(query_row['topics_json'])
    else:
        topics = []

    return render_template("help_view.html", query=query_row, responses=responses, history=history, topics=topics)


def score_response(response_txt, avoid_set):
    ''' Return an integer score for a given response text.
    Returns:
        0 = best.
        Negative values for responses including indications of code blocks or keywords in the avoid set.
        Indications of code blocks are weighted most heavily.
    '''
    score = 0
    for bad_kw in avoid_set:
        score -= response_txt.count(bad_kw)
    for code_indication in ['```', 'should look like', 'should look something like']:
        score -= 100 * response_txt.count(code_indication)

    return score


async def run_query_prompts(api_key, language, code, error, issue):
    ''' Run the given query against the coding help system of prompts.

    Returns a tuple containing:
      1) A list of response objects from the OpenAI completion (to be stored in the database)
      2) A dictionary of response text, potentially including keys 'error', 'insufficient', and 'main'.
    '''
    db = get_db()
    auth = get_session_auth()

    # create "avoid set" from class configuration
    if auth['class_id'] is not None:
        class_id = auth['class_id']
        class_row = db.execute("SELECT * FROM classes WHERE id=?", [class_id]).fetchone()
        class_config = json.loads(class_row['config'])
        avoid_set = set(x.strip() for x in class_config.get('avoid', '').split('\n') if x.strip() != '')
    else:
        avoid_set = set()

    # Launch the "sufficient detail" check concurrently with the main prompt to save time if it comes back as sufficient.
    task_sufficient = asyncio.create_task(
        get_completion(api_key, prompt=prompts.make_sufficient_prompt(language, code, error, issue), model='turbo')
    )

    task_main = asyncio.create_task(
        get_completion(
            api_key,
            prompt=prompts.make_main_prompt(language, code, error, issue, avoid_set),
            model='turbo',
            n=2,
            score_func=lambda x: score_response(x, avoid_set)
        )
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
        cleanup_response, cleanup_response_txt = await get_completion(api_key, prompt=cleanup_prompt, model='davinci')
        responses.append(cleanup_response)
        response_txt = cleanup_response_txt

    if response_sufficient_txt.endswith("OK") or "OK." in response_sufficient_txt or response_sufficient_txt.startswith("Error ("):
        # We're using just the main response.
        return responses, {'main': response_txt}
    else:
        # Give them the request for more information plus the main response, in case it's helpful.
        return responses, {'insufficient': response_sufficient_txt, 'main': response_txt}


def run_query(api_key, language, code, error, issue):
    query_id = record_query(language, code, error, issue)

    responses, texts = asyncio.run(run_query_prompts(api_key, language, code, error, issue))

    record_response(query_id, responses, texts)

    return query_id


def record_query(language, code, error, issue):
    db = get_db()
    auth = get_session_auth()
    role_id = auth['role_id']

    cur = db.execute(
        "INSERT INTO queries (language, code, error, issue, user_id, role_id) VALUES (?, ?, ?, ?, ?, ?)",
        [language, code, error, issue, auth['user_id'], role_id]
    )
    new_row_id = cur.lastrowid
    db.commit()

    return new_row_id


def record_response(query_id, responses, texts):
    db = get_db()

    db.execute(
        "UPDATE queries SET response_json=?, response_text=? WHERE id=?",
        [json.dumps(responses), json.dumps(texts), query_id]
    )
    db.commit()


@bp.route("/request", methods=["POST"])
@login_required
@class_config_required
@with_openai_key()
def help_request(api_key):
    lang_id = int(request.form["lang_id"])
    language = current_app.config["LANGUAGES"][lang_id]
    code = request.form["code"]
    error = request.form["error"]
    issue = request.form["issue"]

    # TODO: limit length of code/error/issue

    query_id = run_query(api_key, language, code, error, issue)

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


@bp.route("/topics/html/<int:query_id>", methods=["GET", "POST"])
@login_required
@class_config_required
@tester_required
@with_openai_key()
def get_topics_html(api_key, query_id):
    topics, query_row = get_topics(api_key, query_id)
    if not topics:
        return render_template("topics_fragment.html", error=True)
    else:
        return render_template("topics_fragment.html", query=query_row, topics=topics)


@bp.route("/topics/raw/<int:query_id>", methods=["GET", "POST"])
@login_required
@class_config_required
@tester_required
@with_openai_key()
def get_topics_raw(api_key, query_id):
    topics, _ = get_topics(api_key, query_id)
    return topics


def get_topics(api_key, query_id):
    query_row, responses = get_query(query_id)

    messages = prompts.make_topics_prompt(
        query_row['language'],
        query_row['code'],
        query_row['error'],
        query_row['issue'],
        responses['main']
    )

    response, response_txt = asyncio.run(get_completion(
        api_key,
        messages=messages,
        model='turbo',
    ))

    # Verify it is actually JSON
    # May be "Error (..." if an API error occurs, or every now and then may get "Here is the JSON: ..." or similar.
    try:
        json.loads(response_txt)
    except json.decoder.JSONDecodeError:
        return None, None

    # Save topics into queries table for the given query
    db = get_db()
    db.execute("UPDATE queries SET topics_json=? WHERE id=?", [response_txt, query_id])
    db.commit()
    # Return a Python list
    topics = json.loads(response_txt)
    return topics, query_row
