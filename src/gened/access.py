# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from flask import (
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.wrappers.response import Response

from .auth import get_auth
from .db import get_db

# For decorator type hints
P = ParamSpec('P')
R = TypeVar('R')


def login_required(f: Callable[P, R]) -> Callable[P, Response | R]:
    '''Redirect to login on this route if user is not logged in.'''
    @wraps(f)
    def decorated_function(*args: P.args, **kwargs: P.kwargs) -> Response | R:
        auth = get_auth()
        if not auth.user:
            flash("Login required.", "warning")
            return redirect(url_for('auth.login', next=request.full_path))
        return f(*args, **kwargs)
    return decorated_function


def instructor_required(f: Callable[P, R]) -> Callable[P, Response | R]:
    @wraps(f)
    def decorated_function(*args: P.args, **kwargs: P.kwargs) -> Response | R:
        auth = get_auth()
        if auth.cur_class is None or auth.cur_class.role != "instructor":
            flash("Instructor login required.", "warning")
            return redirect(url_for('auth.login', next=request.full_path))
        return f(*args, **kwargs)
    return decorated_function


def class_enabled_required(f: Callable[P, R]) -> Callable[P, str | R]:
    @wraps(f)
    def decorated_function(*args: P.args, **kwargs: P.kwargs) -> str | R:
        auth = get_auth()

        if auth.cur_class is None:
            # No active class, no problem
            return f(*args, **kwargs)

        # Otherwise, there's an active class, so we require it to be enabled.
        class_id = auth.cur_class.class_id
        db = get_db()
        class_row = db.execute("SELECT * FROM classes WHERE id=?", [class_id]).fetchone()
        if not class_row['enabled']:
            flash("The current class is archived or disabled.  New requests cannot be made.", "warning")
            return render_template("error.html")

        return f(*args, **kwargs)

    return decorated_function


def admin_required(f: Callable[P, R]) -> Callable[P, Response | R]:
    '''Redirect to login on this route if user is not an admin.'''
    @wraps(f)
    def decorated_function(*args: P.args, **kwargs: P.kwargs) -> Response | R:
        auth = get_auth()
        if not auth.is_admin:
            flash("Login required.", "warning")
            return redirect(url_for('auth.login', next=request.full_path))
        return f(*args, **kwargs)
    return decorated_function


def tester_required(f: Callable[P, R]) -> Callable[P, Response | R]:
    '''Return a 404 on this route (hide it, basically) if user is not a tester.'''
    @wraps(f)
    def decorated_function(*args: P.args, **kwargs: P.kwargs) -> Response | R:
        auth = get_auth()
        if not auth.is_tester:
            abort(404)
        return f(*args, **kwargs)
    return decorated_function
