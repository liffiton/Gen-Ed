# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Instructor-specific functionality and routes.

This module handles operations that should only be available to instructors, including:
- Viewing and managing student data
- Class data management (viewing, exporting, deletion)
- Student role management

All routes in this blueprint require instructor privileges.
For general class operations available to all users, see classes.py.
"""

from sqlite3 import Row

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.wrappers.response import Response

from .auth import get_auth_class, instructor_required
from .classes import switch_class
from .csv import csv_response
from .data_deletion import delete_class_data
from .db import get_db
from .redir import safe_redirect

bp = Blueprint('instructor', __name__, template_folder='templates')

@bp.before_request
@instructor_required
def before_request() -> None:
    """ Apply decorator to protect all instructor blueprint endpoints. """


def get_queries(class_id: int, user: int | None = None) -> list[Row]:
    db = get_db()

    where_clause = "WHERE UNLIKELY(roles.class_id=?)"  # UNLIKELY() to help query planner in older sqlite versions
    params = [class_id]

    if user is not None:
        where_clause += " AND users.id=?"
        params += [user]

    queries = db.execute(f"""
        SELECT
            queries.id,
            users.display_name,
            users.email,
            queries.*
        FROM queries
        JOIN users
            ON queries.user_id=users.id
        JOIN roles
            ON queries.role_id=roles.id
        {where_clause}
        ORDER BY queries.id DESC
    """, params).fetchall()

    return queries


def get_users(class_id: int, for_export: bool = False) -> list[Row]:
    db = get_db()

    users = db.execute(f"""
        SELECT
            {'roles.id AS role_id,' if not for_export else ''}
            users.id,
            users.display_name,
            users.email,
            auth_providers.name AS auth_provider,
            users.auth_name,
            COUNT(queries.id) AS num_queries,
            SUM(CASE WHEN queries.query_time > date('now', '-7 days') THEN 1 ELSE 0 END) AS num_recent_queries,
            roles.active,
            roles.role = "instructor" AS instructor_role
        FROM users
        LEFT JOIN auth_providers ON users.auth_provider=auth_providers.id
        JOIN roles ON roles.user_id=users.id
        LEFT JOIN queries ON queries.role_id=roles.id
        WHERE roles.class_id=?
        GROUP BY users.id
        ORDER BY display_name
    """, [class_id]).fetchall()

    return users


@bp.route("/")
def main() -> str | Response:
    cur_class = get_auth_class()
    class_id = cur_class.class_id

    users = get_users(class_id)

    sel_user_name = None
    sel_user_id = request.args.get('user', type=int)
    if sel_user_id is not None:
        sel_user_row = next(filter(lambda row: row['id'] == int(sel_user_id), users), None)
        if sel_user_row:
            sel_user_name = sel_user_row['display_name']

    queries = get_queries(class_id, sel_user_id)

    return render_template("instructor.html", users=users, queries=queries, user=sel_user_name)


@bp.route("/csv/<string:kind>")
def get_csv(kind: str) -> str | Response:
    if kind not in ('queries', 'users'):
        return abort(404)

    cur_class = get_auth_class()
    class_id = cur_class.class_id
    class_name = cur_class.class_name

    if kind == "queries":
        table = get_queries(class_id)
    elif kind == "users":
        table = get_users(class_id, for_export=True)

    return csv_response(class_name, kind, table)


@bp.route("/role/set_active", methods=["POST"])  # just for url_for in the Javascript code
@bp.route("/role/set_active/<int:role_id>/<int(min=0, max=1):bool_active>", methods=["POST"])
def set_role_active(role_id: int, bool_active: int) -> str:
    db = get_db()
    cur_class = get_auth_class()

    # prevent instructors from mistakenly making themselves not active and locking themselves out
    if role_id == cur_class.role_id:
        return "You cannot make yourself inactive."

    # class_id should be redundant w/ role_id, but without it, an instructor
    # could potentially deactivate a role in someone else's class.
    # only trust class_id from auth, not from user
    class_id = cur_class.class_id

    db.execute("UPDATE roles SET active=? WHERE id=? AND class_id=?", [bool_active, role_id, class_id])
    db.commit()

    return "okay"


@bp.route("/role/set_instructor", methods=["POST"])  # just for url_for in the Javascript code
@bp.route("/role/set_instructor/<int:role_id>/<int(min=0, max=1):bool_instructor>", methods=["POST"])
def set_role_instructor(role_id: int, bool_instructor: int) -> str:
    db = get_db()
    cur_class = get_auth_class()

    # prevent instructors from mistakenly making themselves not instructors and locking themselves out
    if role_id == cur_class.role_id:
        return "You cannot change your own role."

    # class_id should be redundant w/ role_id, but without it, an instructor
    # could potentially deactivate a role in someone else's class.
    # only trust class_id from auth, not from user
    class_id = cur_class.class_id

    new_role = 'instructor' if bool_instructor else 'student'

    db.execute("UPDATE roles SET role=? WHERE id=? AND class_id=?", [new_role, role_id, class_id])
    db.commit()

    return "okay"


@bp.route("/class/delete", methods=["POST"])
def delete_class() -> Response:
    # Require explicit confirmation
    if request.form.get('confirm_delete') != 'DELETE':
        flash("Class deletion requires confirmation. Please type DELETE to confirm.", "warning")
        return safe_redirect(request.referrer, default_endpoint="profile.main")

    db = get_db()
    cur_class = get_auth_class()
    class_id = cur_class.class_id
    assert str(class_id) == str(request.form.get('class_id'))

    # Call application-specific data deletion handler(s)
    delete_class_data(class_id)

    # Deactivate all roles and disable the class
    db.execute("UPDATE roles SET user_id=-1, active = 0 WHERE class_id = ?", [class_id])
    db.execute("UPDATE classes SET name='[deleted]', enabled = 0 WHERE id = ?", [class_id])
    db.execute("DELETE FROM classes_lti WHERE class_id = ?", [class_id])
    db.execute("DELETE FROM classes_user WHERE class_id = ?", [class_id])
    db.execute("UPDATE users SET last_class_id=NULL WHERE last_class_id = ?", [class_id])
    db.commit()
    flash("Class data has been deleted.", "success")

    switch_class(None)
    return redirect(url_for("profile.main"))
