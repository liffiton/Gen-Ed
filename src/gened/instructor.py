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

from .app_data import Filters, get_registered_data_source
from .auth import get_auth_class, instructor_required
from .classes import switch_class
from .csv import csv_response
from .data_deletion import delete_class_data
from .db import get_db
from .auth import get_auth
from .redir import safe_redirect
from .tables import ButtonCol, BoolCol, Col, DataTable, NumCol, UserCol

bp = Blueprint('instructor', __name__, template_folder='templates')

@bp.before_request
@instructor_required
def before_request() -> None:
    """ Apply decorator to protect all instructor blueprint endpoints. """


def _get_class_queries(user_id: int | None = None) -> list[Row]:
    cur_class = get_auth_class()
    class_id = cur_class.class_id

    filters = Filters()
    filters.add('class', class_id)

    if user_id is not None:
        filters.add('user', user_id)

    get_queries = get_registered_data_source('queries').function
    queries = get_queries(filters).fetchall()

    return queries


def _get_class_users(*, for_export: bool = False) -> list[Row]:
    cur_class = get_auth_class()
    class_id = cur_class.class_id

    db = get_db()

    users = db.execute(f"""
        SELECT
            {'roles.id AS role_id,' if not for_export else ''}
            users.id AS id,
            json_array(users.display_name, auth_providers.name, users.display_extra) AS user,
            COUNT(queries.id) AS "#queries",
            SUM(CASE WHEN queries.query_time > date('now', '-7 days') THEN 1 ELSE 0 END) AS "1wk",
            roles.active AS "active?",
            roles.role = "instructor" AS "instructor?"
        FROM users
        LEFT JOIN auth_providers ON users.auth_provider=auth_providers.id
        JOIN roles ON roles.user_id=users.id
        LEFT JOIN queries ON queries.role_id=roles.id
        WHERE roles.class_id=?
        GROUP BY users.id
        ORDER BY users.display_name
    """, [class_id]).fetchall()

    return users

def _get_query_limits_data() -> list[Row]:
    cur_class = get_auth_class()
    class_id = cur_class.class_id
    db = get_db()

    users = db.execute("""
        SELECT
            users.id,
            json_array(users.display_name, auth_providers.name, users.display_extra) AS user,
            users.queries_used,
            classes.max_queries,
            ('<form method="POST" action="/instructor/reset_student_queries/' || users.id || 
             '" style="display:inline"><button class="button is-small is-warning" type="submit">' ||
             '<span class="icon"><i class="fas fa-rotate"></i></span>' ||
             '<span>Reset</span></button></form>') AS reset_button
        FROM users
        LEFT JOIN auth_providers ON users.auth_provider=auth_providers.id
        JOIN roles ON roles.user_id=users.id
        JOIN classes ON roles.class_id=classes.id
        WHERE roles.class_id=? AND roles.role='student'
        ORDER BY users.display_name
    """, [class_id]).fetchall()

    return users


@bp.route("/")
def main() -> str | Response:
    users = _get_class_users()
    users_table = DataTable(
        name='users',
        columns=[NumCol('role_id', hidden=True), NumCol('id', hidden=True), UserCol('user'), NumCol('#queries'), NumCol('1wk'), BoolCol('active?', url=url_for('.set_role_active')), BoolCol('instructor?', url=url_for('.set_role_instructor'))],
        link_col=1,
        link_template='?user=${value}',
        csv_link=url_for('instructor.get_csv', kind='users'),
        data=users,
    )

    queries_limits_table = DataTable(
        name='query_limits',
        columns=[NumCol('id', hidden=True), UserCol('user'), NumCol('queries_used', align="center"), NumCol('max_queries', align="center"), Col('reset_button', kind='html', align="center")],
        data=_get_query_limits_data()
    )

    sel_user_name = None
    sel_user_id = request.args.get('user', type=int)
    if sel_user_id is not None:
        db = get_db()
        sel_user_row = db.execute("SELECT display_name FROM users WHERE users.id=?", [sel_user_id]).fetchone()
        if sel_user_row:
            sel_user_name = sel_user_row['display_name']

    queries_table = get_registered_data_source('queries').table
    queries_table.data = _get_class_queries(sel_user_id)
    queries_table.csv_link = url_for('instructor.get_csv', kind='queries')

    return render_template( "instructor_view.html", users=users_table, queries=queries_table, query_limits=queries_limits_table, user=sel_user_name
)


@bp.route("/csv/<string:kind>")
def get_csv(kind: str) -> str | Response:
    if kind not in ('queries', 'users'):
        return abort(404)

    cur_class = get_auth_class()
    class_name = cur_class.class_name

    if kind == "queries":
        table = _get_class_queries()
    elif kind == "users":
        table = _get_class_users(for_export=True)

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

@bp.route("/class/config/save", methods=["POST"])
def save_class_config() -> Response:
    db = get_db()
    cur_class = get_auth_class()  # Use get_auth_class() instead of get_auth()
    class_id = cur_class.class_id

    query_limit_enabled = 'query_limit_enabled' in request.form
    max_queries = int(request.form.get('max_queries', 50))  # Default to 50 if not provided

    db.execute("""
        UPDATE classes
        SET query_limit_enabled = ?, max_queries = ?
        WHERE id = ?
    """, [query_limit_enabled, max_queries, class_id])
    db.commit()

    flash("Class configuration updated.", "success")
    return redirect(url_for("class_config.config_form"))

@bp.route("/class/reset_queries", methods=["POST"])
def reset_queries() -> Response:
    db = get_db()
    cur_class = get_auth_class()  # Use get_auth_class() instead of get_auth()
    class_id = cur_class.class_id

    db.execute("""
        UPDATE users 
        SET queries_used = 0 
        WHERE id IN (
            SELECT user_id 
            FROM roles 
            WHERE class_id = ? AND role = 'student'
        )
    """, [class_id])
    db.commit()

    flash("Query counts reset for all students.", "success")
    return redirect(url_for("instructor.main"))  # Redirect to instructor main page

@bp.route("/reset_student_queries/<int:user_id>", methods=["POST"])
def reset_student_queries(user_id: int) -> Response:
    db = get_db()
    cur_class = get_auth_class()
    class_id = cur_class.class_id

    # Verify user belongs to class and is a student
    student = db.execute("""
        SELECT users.id 
        FROM users 
        JOIN roles ON roles.user_id = users.id 
        WHERE users.id = ? AND roles.class_id = ? AND roles.role = 'student'
    """, [user_id, class_id]).fetchone()

    if not student:
        flash("Invalid student ID.", "error")
        return redirect(url_for("instructor.main"))

    # Reset queries for student
    db.execute(
        "UPDATE users SET queries_used = 0 WHERE id = ?",
        [user_id]
    )
    db.commit()

    flash("Query count reset for student.", "success")
    return redirect(url_for("instructor.main"))

@bp.route("/reset_all_queries", methods=["POST"])
def reset_all_queries() -> Response:
    db = get_db()
    cur_class = get_auth_class()
    class_id = cur_class.class_id

    # Reset queries for all students in class
    db.execute("""
        UPDATE users 
        SET queries_used = 0 
        WHERE id IN (
            SELECT user_id 
            FROM roles 
            WHERE class_id = ? AND role = 'student'
        )
    """, [class_id])
    db.commit()

    flash("Query counts reset for all students.", "success")
    return redirect(url_for("instructor.main"))