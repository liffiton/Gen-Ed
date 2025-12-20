# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from collections.abc import Callable
from enum import Flag, auto
from functools import wraps
from typing import ParamSpec, TypeVar

from flask import (
    abort,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.wrappers.response import Response

from .auth import AuthData, get_auth


# Access levels.
# Any blueprint, route, or bit of functionality may require one or more of these.
class Access(Flag):
    LOGIN = auto()
    INSTRUCTOR = auto()
    ADMIN = auto()
    TESTER = auto()
    CLASS_ENABLED = auto()


def check_login(auth: AuthData) -> Response | None:
    '''Redirect to login if user is not logged in.'''
    if not auth.user:
        flash("Login required.", "warning")
        return redirect(url_for('auth.login', next=request.full_path))
    return  None


def check_instructor(auth: AuthData) -> Response | None:
    '''Redirect to login if user is not an instructor in the current class.'''
    if auth.cur_class is None or auth.cur_class.role != "instructor":
        flash("Instructor login required.", "warning")
        return redirect(url_for('auth.login', next=request.full_path))
    return None


def check_admin(auth: AuthData) -> Response | None:
    '''Redirect to login if user is not an admin.'''
    if not auth.is_admin:
        flash("Login required.", "warning")
        return redirect(url_for('auth.login', next=request.full_path))
    return None


def check_tester(auth: AuthData) -> None:
    '''Hide the route if user is not a tester.'''
    if not auth.is_tester:
        abort(404)


def check_class_enabled(auth: AuthData) -> Response | None:
    '''Display an error if there is an active class but it is not enabled.'''
    if auth.cur_class is None:
        # No active class, no problem
        return None

    # Otherwise, there's an active class, so we require it to be enabled.
    if not auth.cur_class.class_enabled:
        flash("The current class is archived or disabled.  New requests cannot be made.", "warning")
        return make_response(render_template("error.html"))

    return None


# Checks will be made in the order they are stored in this dict
# (relying on dicts keeping/using insertion order)
ACCESS_CHECKS: dict[Access, Callable[[AuthData], Response | None]] = {
    Access.LOGIN: check_login,
    Access.INSTRUCTOR: check_instructor,
    Access.ADMIN: check_admin,
    Access.TESTER: check_tester,
    Access.CLASS_ENABLED: check_class_enabled,
}


def check_access(required: Access) -> Response | None:
    """
    Check if user meets the required access levels.
    Redirects with flash message if access denied.

    Args:
        required: Combined Access flags to check

    Returns:
        Response object if access denied, None otherwise
    """
    auth = get_auth()

    for level, check_func in ACCESS_CHECKS.items():
        if level in required:
            result = check_func(auth)
            if result is not None:
                return result

    return None


# For decorator type hints
P = ParamSpec('P')
R = TypeVar('R')

def require_access(required: Access) -> Callable[[Callable[P, R]], Callable[P, Response | R]]:
    """Decorator that checks if user meets access requirements for a single route."""
    def decorator(f: Callable[P, R]) -> Callable[P, Response | R]:
        @wraps(f)
        def decorated_function(*args: P.args, **kwargs: P.kwargs) -> Response | R:
            result = check_access(required)
            if result is not None:
                return result
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# Define existing decorators for backwards-compatibility
# (TODO: phase these out, use require_access directly)
login_required = require_access(Access.LOGIN)
instructor_required = require_access(Access.INSTRUCTOR)
admin_required = require_access(Access.ADMIN)
tester_required = require_access(Access.TESTER)
class_enabled_required = require_access(Access.CLASS_ENABLED)

