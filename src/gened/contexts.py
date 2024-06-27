# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import json
from collections.abc import Callable
from dataclasses import Field, asdict
from functools import wraps
from sqlite3 import Row
from typing import Any, ClassVar, ParamSpec, TypeVar

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from typing_extensions import Protocol, Self
from werkzeug.datastructures import ImmutableMultiDict
from werkzeug.wrappers.response import Response

from .auth import get_auth
from .db import get_db

# This module handles common class configuration (access control, LLM
# selection) and also provides a generic interface to manage
# application-specific class configuration.
#
# Any application can register a ContextConfig dataclass with this module using
# `register_context()` to add an application-specific section for contexts to
# the instructor class configuration form.  The application itself must provide
# a template for a context configuration create/update form (specified in the
# `template` attribute of the dataclass).  Routes in this module handle that
# form's rendering and submission.  The application itself must implement any
# other logic for using the contexts throughout the app.
#
# App-specific context configuration data are stored in dataclasses.  The
# dataclass must specify the template filename, contain the context's name,
# define the config's fields and their types, and implement a
# `from_request_form()` class method that generates a config object based on
# inputs in request.form (as submitted from the form in the specified
# template).

# For type checking classes for storing a class configuration:
class ContextConfig(Protocol):
    # Must contain a template attribute with the name of a template file
    template: str
    # Must contain a name attribute
    name: str
    # So it looks like a dataclass:
    __dataclass_fields__: ClassVar[dict[str, Field[Any]]]

    # Instantiate from a request form (must be implemented by application):
    @classmethod
    def from_request_form(cls, form: ImmutableMultiDict[str, str]) -> Self:
        ...

    # Instantiate from an SQLite row (implemented here) (requires correct field
    # names in the row and in its 'config' entry JSON)
    @classmethod
    def from_row(cls, row: Row) -> Self:
        attrs = json.loads(row['config'])
        attrs['name'] = row['name']
        return cls(**attrs)

    # Dump config data (all but name and template) to JSON (implemented here)
    def to_json(self) -> str:
        filtered_attrs = {k: v for k, v in asdict(self).items() if k not in ('name', 'template')}
        return json.dumps(filtered_attrs)


# Store a registered config class.
_context_class: type[ContextConfig] | None = None

def register_context(cls: type[ContextConfig]) -> type[ContextConfig]:
    """ Register a context configuration dataclass with this module.
    Used by each specific application that needs app-specific contexts.
    May be used as a decorator (returns the given class unmodified).
    """
    global _context_class  # noqa: PLW0603 (global statement)
    _context_class = cls
    return cls


def have_registered_context() -> bool:
    return _context_class is not None


# For decorator type hints
P = ParamSpec('P')
R = TypeVar('R')

def context_required(f: Callable[P, R]) -> Callable[P, Response | R]:
    """ Decorator to wrap a route and make it return a 404 if no context config
    class is registered.

    Assigns a `ctx_class` named argument carrying the registered class.
    """
    @wraps(f)
    def decorated_function(*args: P.args, **kwargs: P.kwargs) -> Response | R:
        if not have_registered_context():
            return abort(404)
        kwargs['ctx_class'] = _context_class
        return f(*args, **kwargs)
    return decorated_function


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
        auth = get_auth()

        # verify the given context is in the user's current class
        class_id = auth['class_id']
        ctx_id = kwargs['ctx_id']
        context_row = db.execute("SELECT * FROM contexts WHERE id=?", [ctx_id]).fetchone()
        if context_row['class_id'] != class_id:
            return abort(403)

        kwargs['ctx_row'] = context_row
        return f(*args, **kwargs)
    return decorated_function


### Blueprint + routes

# Should be registered under class_config.bp
# Will be protected by @instructor_required applied to
# class_config.bp.before_request()
bp = Blueprint('contexts', __name__, url_prefix="/context", template_folder='templates')


@bp.route("/edit/", methods=[])  # just for url_for() in js code
@bp.route("/edit/<int:ctx_id>")
@context_required
@check_valid_context
def context_form(ctx_class: type[ContextConfig], ctx_row: Row, ctx_id: int) -> str | Response:  # noqa: ARG001 - ctx_id required/provided by route
    context_config = ctx_class.from_row(ctx_row)
    return render_template(context_config.template, context=ctx_row, context_config=context_config)


@bp.route("/new")
@context_required
def new_context_form(ctx_class: type[ContextConfig]) -> str | Response:
    return render_template(ctx_class.template, context=None, context_config=None)


def _insert_context(class_id: int, name: str, config: str, available: str) -> int:
    db = get_db()

    # names must be uniquie within a class: check/look for an unused name
    new_name = name
    i = 0
    while db.execute("SELECT id FROM contexts WHERE class_id=? AND name=?", [class_id, new_name]).fetchone():
        i += 1
        new_name = f"{name} ({i})"

    cur = db.execute("""
        INSERT INTO contexts (class_id, name, config, available, class_order)
        VALUES (?, ?, ?, ?, (SELECT COALESCE(MAX(class_order)+1, 0) FROM contexts WHERE class_id=?))
    """, [class_id, new_name, config, available, class_id])
    db.commit()
    new_ctx_id = cur.lastrowid

    flash(f"Context '{new_name}' created.", "success")

    return new_ctx_id


@bp.route("/create", methods=["POST"])
@context_required
def create_context(ctx_class: type[ContextConfig]) -> Response:
    auth = get_auth()
    assert auth['class_id']

    context = ctx_class.from_request_form(request.form)
    _insert_context(auth['class_id'], context.name, context.to_json(), "0001-01-01")
    return redirect(url_for("class_config.config_form"))


@bp.route("/copy/", methods=[])  # just for url_for() in js code
@bp.route("/copy/<int:ctx_id>", methods=["POST"])
@context_required
@check_valid_context
def copy_context(ctx_class: type[ContextConfig], ctx_row: Row, ctx_id: int) -> Response:
    auth = get_auth()
    assert auth['class_id']

    # passing existing name, but _insert_context will take care of finding
    # a new, unused name in the class.
    _insert_context(auth['class_id'], ctx_row['name'], ctx_row['config'], ctx_row['available'])
    return redirect(url_for("class_config.config_form"))


@bp.route("/update/<int:ctx_id>", methods=["POST"])
@context_required
@check_valid_context
def update_context(ctx_class: type[ContextConfig], ctx_id: int, ctx_row: Row) -> Response:
    db = get_db()

    context = ctx_class.from_request_form(request.form)

    db.execute("UPDATE contexts SET name=?, config=? WHERE id=?", [context.name, context.to_json(), ctx_id])
    db.commit()

    flash(f"Configuration for context '{ctx_row['name']}' updated.", "success")
    return redirect(url_for("class_config.config_form"))


@bp.route("/delete/", methods=[])  # just for url_for() in js code
@bp.route("/delete/<int:ctx_id>", methods=["POST"])
@context_required
@check_valid_context
def delete_context(ctx_class: type[ContextConfig], ctx_id: int, ctx_row: Row) -> Response:
    db = get_db()

    db.execute("DELETE FROM contexts WHERE id=?", [ctx_id])
    db.commit()

    flash(f"Configuration for context '{ctx_row['name']}' deleted.", "success")
    return redirect(url_for("class_config.config_form"))


### Helper functions for applications

T = TypeVar('T', bound='ContextConfig')

def get_available_contexts(ctx_class: type[T]) -> list[T]:
    db = get_db()
    auth = get_auth()

    class_id = auth['class_id']
    # TODO: filter by available using current date
    context_rows = db.execute("SELECT * FROM contexts WHERE class_id=? ORDER BY class_order ASC", [class_id]).fetchall()

    return [ctx_class.from_row(row) for row in context_rows]


class ContextNotFoundError(Exception):
    pass


def get_context_config_by_id(ctx_class: type[T], ctx_id: int) -> T:
    assert _context_class is not None

    db = get_db()
    auth = get_auth()

    class_id = auth['class_id']  # just for extra safety: double-check that the context is in the current class

    context_row = db.execute("SELECT * FROM contexts WHERE class_id=? AND id=?", [class_id, ctx_id]).fetchone()

    if not context_row:
        raise ContextNotFoundError

    return ctx_class.from_row(context_row)


def get_context_by_name(ctx_class: type[T], ctx_name: str) -> T:
    assert _context_class is not None

    db = get_db()
    auth = get_auth()

    class_id = auth['class_id']

    context_row = db.execute("SELECT * FROM contexts WHERE class_id=? AND name=?", [class_id, ctx_name]).fetchone()

    if not context_row:
        raise ContextNotFoundError

    return ctx_class.from_row(context_row)
