# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from functools import wraps
from typing import ParamSpec, TypeVar, assert_never

from flask import (
    Blueprint,
    current_app,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.wrappers.response import Response

from .auth import get_auth

# Access controls.
# Any blueprint, route, or bit of functionality may require one or more of these conditions.
# Using Enum for the simple (non-data-carrying) kinds; dataclasses for those carrying data.

class Access(Enum):
    LOGIN = auto()          # User is logged in
    CLASS_ENABLED = auto()  # User's current class is enabled (or there is no current class)
    INSTRUCTOR = auto()     # User has an instructor role in the current class
    ADMIN = auto()          # User is an admin
    TESTER = auto()         # User is a tester

# User's current class is included in the named experiment (or user is an admin)
@dataclass
class RequireExperiment:
    name: str

# The given component is enabled in the user's current class
@dataclass
class RequireComponent:
    name: str  # the name of a component that must be registered (under that name), available, and enabled
    feature: str | None = None  # (optional) the name of a feature of the component that must also be enabled

# Combined access control type for use when specifying requirements
AccessControl = Access | RequireExperiment | RequireComponent


def check_one_access_control(control: AccessControl) -> bool:  # noqa: PLR0911 - lots of return stmts needed here
    auth = get_auth()

    match control:
        case Access.LOGIN:
            return auth.user is not None
        case Access.CLASS_ENABLED:
            return auth.cur_class is None or auth.cur_class.class_enabled  # no current class also okay
        case Access.INSTRUCTOR:
            return auth.cur_class is not None and auth.cur_class.role == "instructor"
        case Access.ADMIN:
            return auth.is_admin
        case Access.TESTER:
            return auth.is_tester
        case RequireExperiment(name=name):
            return name in auth.class_experiments or auth.is_admin  # admins are allowed to access any experiment anywhere
        case RequireComponent(name=name, feature=feature):
            from .component_registry import get_component_registry  # noqa: PLC0415, I001 - import moved here to avoid a messy circular import issue
            component = get_component_registry().get(name)
            return component is not None and component.is_available() and component.is_enabled(feature=feature)

    assert_never(control)  # ensure above is exhaustive


def _find_first_failed_access_control(*required: AccessControl) -> AccessControl | None:
    """
    Check a set of required access controls.

    Args:
        A variable number of AccessControl values, each specifying one control to apply.

    If a specific AccessControl check fails, returns that AccessControl.
    Returns None otherwise.
    """
    for control in required:
        if not check_one_access_control(control):
            return control

    return None


def check_access(*required: AccessControl) -> bool:
    """
    Check a set of required access controls.

    Args:
        A variable number of AccessControl values, each specifying one control to apply.

    Returns True if all pass, False otherwise.
    Uses internal _find_first_failed... function to implement correct/consistent check logic.
    """
    return _find_first_failed_access_control(*required) is None


def _handle_route_check_failure(control_type: AccessControl) -> Response:
    """ Handle the failure of a given access control check for a route request. """
    auth = get_auth()
    if auth.user is None or control_type == Access.LOGIN:
        # all checks redirect to login if the user is not logged in already
        # (included redundant Access.LOGIN in condition for type checker to know it's covered)
        flash("Login required.", "warning")
        return redirect(url_for('auth.login', next=request.full_path))

    current_app.logger.warning(f"Access check failed: {control_type=} url={request.url} {auth=}")

    match control_type:
        case Access.INSTRUCTOR | Access.ADMIN | Access.TESTER:
            # error 403 Forbidden if user has wrong role.
            flash("Access denied.  You do not have permission to perform this action.", "warning")
            return make_response(render_template("error.html"), 403)
        case Access.CLASS_ENABLED:
            # error 403 Forbidden with a specific error message if there is an active class but it is not enabled.
            flash("The current class is archived or disabled.  New requests cannot be made.", "warning")
            return make_response(render_template("error.html"), 403)
        case RequireExperiment() | RequireComponent():
            # error 403 Forbidden with a specific error message if the required experiment or component is not active/enabled
            flash("Cannot access the specified resource.", "warning")
            flash(f"Make sure you log in to {current_app.config['APPLICATION_TITLE']} from the correct class before using this link.", "warning")
            return make_response(render_template("error.html"), 403)

    assert_never(control_type)  # ensure above is exhaustive


# For decorator type hints
P = ParamSpec('P')
R = TypeVar('R')

def route_requires(*required: AccessControl) -> Callable[[Callable[P, R]], Callable[P, Response | R]]:
    """
    Decorator that checks if user meets access requirements for a single route.

    Args:
        A variable number of AccessControl values, each specifying one control to apply.

    The decorated function returns a specific check failure response if any requirement fails.
    """
    def decorator(f: Callable[P, R]) -> Callable[P, Response | R]:
        @wraps(f)
        def decorated_function(*args: P.args, **kwargs: P.kwargs) -> Response | R:
            failed_control = _find_first_failed_access_control(*required)
            if failed_control is None:
                return f(*args, **kwargs)
            else:
                return _handle_route_check_failure(failed_control)
        return decorated_function
    return decorator

# Define existing decorators for backwards-compatibility
# (TODO: phase these out, use route_requires directly)
login_required = route_requires(Access.LOGIN)
instructor_required = route_requires(Access.INSTRUCTOR)
admin_required = route_requires(Access.ADMIN)
tester_required = route_requires(Access.TESTER)
class_enabled_required = route_requires(Access.CLASS_ENABLED)


def control_blueprint_access(bp: Blueprint, *required: AccessControl) -> None:
    """
    Applies access requirements to every route in a given blueprint.

    Args:
        bp: A Flask blueprint to which to add access controls.
        *required: A variable number of AccessControl values, each specifying one control to apply.

    Modifies the blueprint in place, updating its `before_request` to add access control to every route.
    """
    @bp.before_request
    @route_requires(*required)
    def protect_all_routes() -> None:
        pass

