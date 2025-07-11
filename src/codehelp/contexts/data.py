# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only


from gened.auth import get_auth
from gened.db import get_db

from .model import ContextConfig

### Helper functions for using contexts

def get_available_contexts() -> list[ContextConfig]:
    db = get_db()
    auth = get_auth()

    class_id = auth.cur_class.class_id if auth.cur_class else None
    # Only return contexts that are available:
    #   current date anywhere on earth (using UTC+12) is at or after the saved date
    context_rows = db.execute("SELECT * FROM contexts WHERE class_id=? AND available <= date('now', '+12 hours') ORDER BY class_order ASC", [class_id]).fetchall()

    return [ContextConfig.from_row(row) for row in context_rows]


def get_context_string_by_id(ctx_id: int) -> str | None:
    """ Return a context string based on the specified id
        or return None if no context string exists with that id.
    """
    db = get_db()
    auth = get_auth()

    if auth.is_admin:
        # admin can grab any context
        context_row = db.execute("SELECT * FROM context_strings WHERE id=?", [ctx_id]).fetchone()
    else:
        # for non-admin users, double-check that the context is in the current class
        class_id = auth.cur_class.class_id if auth.cur_class else None
        context_row = db.execute("SELECT * FROM context_strings WHERE class_id=? AND id=?", [class_id, ctx_id]).fetchone()

    if not context_row:
        return None

    return str(context_row['ctx_str'])


def get_context_by_name(ctx_name: str) -> ContextConfig | None:
    """ Return a context object of the given class based on the specified name
        or return None if no context exists with that name.
    """
    db = get_db()
    auth = get_auth()

    class_id = auth.cur_class.class_id if auth.cur_class else None

    context_row = db.execute("SELECT * FROM contexts WHERE class_id=? AND name=?", [class_id, ctx_name]).fetchone()

    if not context_row:
        return None

    return ContextConfig.from_row(context_row)


def record_context_string(context_str: str) -> int:
    """ Ensure a context string is recorded in the context_strings
        table, and return its row ID.
    """
    db = get_db()
    # Add the context string to the context_strings table, but if it's a duplicate, just get the row ID of the existing one.
    # The "UPDATE SET id=id" is a no-op, but it allows the "RETURNING" to work in case of a conflict as well.
    cur = db.execute("INSERT INTO context_strings (ctx_str) VALUES (?) ON CONFLICT DO UPDATE SET id=id RETURNING id", [context_str])
    context_string_id = cur.fetchone()['id']
    assert isinstance(context_string_id, int)
    return context_string_id


def _get_instructor_courses(user_id: int, current_class_id: int) -> list[dict[str, str | list[str]]]:
    """ Get other courses where the user is an instructor. """
    db = get_db()
    course_rows = db.execute("""
        SELECT c.id, c.name
        FROM classes c
        JOIN roles r ON c.id = r.class_id
        WHERE r.user_id = ?
          AND r.role = 'instructor'
          AND c.id != ?
        ORDER BY c.name
    """, [user_id, current_class_id]).fetchall()

    # Fetch contexts for each eligible course to display in the copy modal
    instructor_courses_data = []
    for course in course_rows:
        course_contexts = db.execute("""
            SELECT name FROM contexts WHERE class_id = ? ORDER BY class_order
        """, [course['id']]).fetchall()
        instructor_courses_data.append({
            'id': course['id'],
            'name': course['name'],
            'contexts': [ctx['name'] for ctx in course_contexts]
        })

    return instructor_courses_data
