import json
import markdown

from flask import flash

from shared.db import get_db
from shared.auth import get_session_auth


def get_query(query_id):
    db = get_db()
    auth = get_session_auth()

    query_row = None
    response_html_dict = None

    if auth['is_admin']:
        cur = db.execute("SELECT queries.*, users.username FROM queries JOIN users ON queries.user_id=users.id WHERE queries.id=?", [query_id])
    elif auth['lti'] is not None and auth['lti']['role'] == 'instructor':
        cur = db.execute("SELECT queries.*, users.username FROM queries JOIN users ON queries.user_id=users.id JOIN roles ON queries.role_id=roles.id WHERE (roles.class_id=? OR queries.user_id=?) AND queries.id=?", [auth['lti']['class_id'], auth['user_id'], query_id])
    else:
        cur = db.execute("SELECT queries.*, users.username FROM queries JOIN users ON queries.user_id=users.id WHERE queries.user_id=? AND queries.id=?", [auth['user_id'], query_id])
    query_row = cur.fetchone()

    if query_row:
        if query_row['response_text']:
            text_dict = json.loads(query_row['response_text'])
            response_html_dict = {
                key: markdown.markdown(text, output_format="html5", extensions=['fenced_code', 'sane_lists', 'smarty'])
                for key, text in text_dict.items()
            }
        else:
            response_html_dict = {'error': "<i>No response -- an error occurred.  Please try again.</i>"}
    else:
        flash("Invalid id.", "warning")

    return query_row, response_html_dict


def get_history(limit=10):
    '''Fetch current user's query history.'''
    db = get_db()
    auth = get_session_auth()

    cur = db.execute("SELECT * FROM queries WHERE queries.user_id=? ORDER BY query_time DESC LIMIT ?", [auth['user_id'], limit])
    history = cur.fetchall()
    return history
