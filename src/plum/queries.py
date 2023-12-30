# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import json
from sqlite3 import Row

from flask import flash

from .auth import get_auth
from .db import get_db


def get_query(query_id: int) -> tuple[Row, dict[str, str]] | tuple[None, None]:
    db = get_db()
    auth = get_auth()

    query_row = None

    if auth['is_admin']:
        cur = db.execute("SELECT queries.*, users.display_name FROM queries JOIN users ON queries.user_id=users.id WHERE queries.id=?", [query_id])
    elif auth['role'] == 'instructor':
        cur = db.execute("SELECT queries.*, users.display_name FROM queries JOIN users ON queries.user_id=users.id JOIN roles ON queries.role_id=roles.id WHERE (roles.class_id=? OR queries.user_id=?) AND queries.id=?", [auth['class_id'], auth['user_id'], query_id])
    else:
        cur = db.execute("SELECT queries.*, users.display_name FROM queries JOIN users ON queries.user_id=users.id WHERE queries.user_id=? AND queries.id=?", [auth['user_id'], query_id])
    query_row = cur.fetchone()

    if not query_row:
        flash("Invalid id.", "warning")
        return None, None

    if query_row['response_text']:
        responses = json.loads(query_row['response_text'])
    else:
        responses = {'error': "*No response -- an error occurred.  Please try again.*"}
    return query_row, responses



def get_history(limit: int = 10) -> list[Row]:
    '''Fetch current user's query history.'''
    db = get_db()
    auth = get_auth()

    cur = db.execute("SELECT * FROM queries WHERE queries.user_id=? ORDER BY query_time DESC LIMIT ?", [auth['user_id'], limit])
    history = cur.fetchall()
    return history
