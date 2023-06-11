import json

from flask import flash

from .db import get_db
from .auth import get_session_auth


def get_query(query_id):
    db = get_db()
    auth = get_session_auth()

    query_row = None

    if auth['is_admin']:
        cur = db.execute("SELECT queries.*, users.email FROM queries JOIN users ON queries.user_id=users.id WHERE queries.id=?", [query_id])
    elif auth['lti'] is not None and auth['lti']['role'] == 'instructor':
        cur = db.execute("SELECT queries.*, users.email FROM queries JOIN users ON queries.user_id=users.id JOIN roles ON queries.role_id=roles.id WHERE (roles.class_id=? OR queries.user_id=?) AND queries.id=?", [auth['lti']['class_id'], auth['user_id'], query_id])
    else:
        cur = db.execute("SELECT queries.*, users.email FROM queries JOIN users ON queries.user_id=users.id WHERE queries.user_id=? AND queries.id=?", [auth['user_id'], query_id])
    query_row = cur.fetchone()

    if query_row:
        if query_row['response_text']:
            responses = json.loads(query_row['response_text'])
        else:
            responses = {'error': "*No response -- an error occurred.  Please try again.*"}
    else:
        flash("Invalid id.", "warning")
        responses = None

    return query_row, responses


def get_history(limit=10):
    '''Fetch current user's query history.'''
    db = get_db()
    auth = get_session_auth()

    cur = db.execute("SELECT * FROM queries WHERE queries.user_id=? ORDER BY query_time DESC LIMIT ?", [auth['user_id'], limit])
    history = cur.fetchall()
    return history
