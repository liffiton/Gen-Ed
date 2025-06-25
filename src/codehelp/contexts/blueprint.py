# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from collections.abc import Callable
from functools import wraps
from sqlite3 import Row
from typing import ParamSpec, TypeVar

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.wrappers.response import Response

from gened.auth import get_auth, get_auth_class, instructor_required
from gened.db import get_db

from .model import ContextConfig

# For decorator type hints
P = ParamSpec('P')
R = TypeVar('R')

def check_valid_context(f: Callable[P, R]) -> Callable[P, Response | R]:
    """ Decorator to wrap a route that takes a ctx_id parameter and make it
    return a 403 if that is not a contxt in the current class.

    Typically used with @instructor_required, in which case this guarantees the
    current user is allowed to edit the specified context.

    Assigns a `ctx_row` named argument carrying the context's db row.
    """
    @wraps(f)
    def decorated_function(*args: P.args, **kwargs: P.kwargs) -> Response | R:
        db = get_db()
        cur_class = get_auth_class()

        # verify the given context is in the user's current class
        class_id = cur_class.class_id
        ctx_id = kwargs['ctx_id']
        context_row = db.execute("SELECT * FROM contexts WHERE id=?", [ctx_id]).fetchone()
        if context_row['class_id'] != class_id:
            abort(403)

        kwargs['ctx_row'] = context_row
        return f(*args, **kwargs)
    return decorated_function


bp = Blueprint('context_config', __name__, url_prefix="/instructor/context", template_folder='templates')

@bp.before_request
@instructor_required
def before_request() -> None:
    """ Apply decorator to protect all class_config blueprint endpoints. """


@bp.route("/edit/", methods=[])  # just for url_for() in js code
@bp.route("/edit/<int:ctx_id>")
@check_valid_context
def context_form(ctx_row: Row, ctx_id: int) -> str | Response:  # noqa: ARG001 - ctx_id required/provided by route
    context_config = ContextConfig.from_row(ctx_row)
    return render_template(context_config.template, context=ctx_row, context_config=context_config)


@bp.route("/new")
def new_context_form() -> str | Response:
    return render_template(ContextConfig.template, context=None, context_config=None)


def _make_unique_context_name(class_id: int, name: str, ctx_id: int = -1) -> str:
    """ Given a class and a potential context name, return a context name that
        is unique within that class.
        (Yes, there's a race condition when using this.  Worst-case, the
        database constraints will error out an invalid insert or update.)

        If ctx_id is provided, then allow the name to match that row's existing name.
        (Used in an update, where the new name just can't match any *other* row's names.)
    """
    db = get_db()

    new_name = name
    i = 0
    # if ctx_id is -1 (the default), then the id!= constraint will always be True.
    while db.execute("SELECT id FROM contexts WHERE class_id=? AND name=? AND id!=?", [class_id, new_name, ctx_id]).fetchone():
        i += 1
        new_name = f"{name} ({i})"

    return new_name


def _insert_context(class_id: int, name: str, config: str, available: str) -> int:
    db = get_db()

    # names must be unique within a class: check/look for an unused name
    new_name = _make_unique_context_name(class_id, name)

    cur = db.execute("""
        INSERT INTO contexts (class_id, name, config, available, class_order)
        VALUES (?, ?, ?, ?, (SELECT COALESCE(MAX(class_order)+1, 0) FROM contexts WHERE class_id=?))
    """, [class_id, new_name, config, available, class_id])
    db.commit()
    new_ctx_id = cur.lastrowid
    assert new_ctx_id is not None

    flash(f"Context '{new_name}' created.", "success")

    return new_ctx_id


@bp.route("/create", methods=["POST"])
def create_context() -> Response:
    cur_class = get_auth_class()

    context = ContextConfig.from_request_form(request.form)
    _insert_context(cur_class.class_id, context.name, context.to_json(), "9999-12-31")  # defaults to hidden
    return redirect(url_for("class_config.config_form"))


@bp.route("/copy_from_course", methods=["POST"])
def copy_from_course() -> Response:
    db = get_db()
    auth = get_auth()
    assert auth.user
    cur_class = get_auth_class()
    target_class_id = cur_class.class_id

    source_class_id = int(request.form['source_class_id'])

    # --- Security Check ---
    # Verify the current user is actually an instructor in the source course
    is_source_instructor = db.execute("""
        SELECT 1 FROM roles
        WHERE user_id = ? AND class_id = ? AND role = 'instructor' AND active = 1
    """, [auth.user.id, source_class_id]).fetchone()
    if not is_source_instructor:
        current_app.logger.warning(f"User {auth.user.id} attempted to copy contexts from class {source_class_id} without instructor role.")
        abort(403) # User is not instructor in source course
    # --- End Security Check ---

    source_contexts = db.execute("SELECT * FROM contexts WHERE class_id = ? ORDER BY class_order", [source_class_id]).fetchall()
    source_class_name = db.execute("SELECT name FROM classes WHERE id = ?", [source_class_id]).fetchone()['name']

    if not source_contexts:
        flash(f"Course '{source_class_name}' has no contexts to copy.", "warning")
        return redirect(url_for("class_config.config_form"))

    for ctx_row in source_contexts:
        _insert_context(target_class_id, ctx_row['name'], ctx_row['config'], "9999-12-31")  # default to hidden
    flash(f"Successfully copied {len(source_contexts)} context(s) from '{source_class_name}'.", "success")

    return redirect(url_for("class_config.config_form"))


@bp.route("/copy/", methods=[])  # just for url_for() in js code
@bp.route("/copy/<int:ctx_id>", methods=["POST"])
@check_valid_context
def copy_context(ctx_row: Row, ctx_id: int) -> Response:
    cur_class = get_auth_class()

    # passing existing name, but _insert_context will take care of finding
    # a new, unused name in the class.
    _insert_context(cur_class.class_id, ctx_row['name'], ctx_row['config'], ctx_row['available'])
    return redirect(url_for("class_config.config_form"))


@bp.route("/update/<int:ctx_id>", methods=["POST"])
@check_valid_context
def update_context(ctx_id: int, ctx_row: Row) -> Response:
    db = get_db()

    context = ContextConfig.from_request_form(request.form)

    # names must be unique within a class: check/look for an unused name
    cur_class = get_auth_class()
    name = _make_unique_context_name(cur_class.class_id, context.name, ctx_id)

    db.execute("UPDATE contexts SET name=?, config=? WHERE id=?", [name, context.to_json(), ctx_id])
    db.commit()

    flash(f"Configuration for context '{ctx_row['name']}' updated.", "success")
    return redirect(url_for("class_config.config_form"))


@bp.route("/delete/", methods=[])  # just for url_for() in js code
@bp.route("/delete/<int:ctx_id>", methods=["POST"])
@check_valid_context
def delete_context(ctx_id: int, ctx_row: Row) -> Response:
    db = get_db()

    db.execute("DELETE FROM contexts WHERE id=?", [ctx_id])
    db.commit()

    flash(f"Context '{ctx_row['name']}' deleted.", "success")
    return redirect(url_for("class_config.config_form"))


@bp.route("/update_order", methods=["POST"])
def update_order() -> str:
    db = get_db()
    cur_class = get_auth_class()

    class_id = cur_class.class_id  # Get the current class to ensure we don't change another class.

    ordered_ids = request.json
    assert isinstance(ordered_ids, list)
    sql_tuples = [(i, ctx_id, class_id) for i, ctx_id in enumerate(ordered_ids)]

    # Check class_id in the WHERE to prevent changing contexts in another class
    db.executemany("UPDATE contexts SET class_order=? WHERE id=? AND class_id=?", sql_tuples)
    db.commit()

    return 'ok'


@bp.route("/update_available", methods=["POST"])
def update_available() -> str:
    db = get_db()
    cur_class = get_auth_class()

    class_id = cur_class.class_id  # Get the current class to ensure we don't change another class.

    data = request.json
    assert isinstance(data, dict)

    # Check class_id in the WHERE to prevent changing contexts in another class
    db.execute("UPDATE contexts SET available=? WHERE id=? AND class_id=?", [data['available'], data['ctx_id'], class_id])
    db.commit()

    return 'ok'
