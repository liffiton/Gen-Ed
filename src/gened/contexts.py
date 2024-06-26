# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import json
from collections.abc import Callable
from dataclasses import Field, asdict
from functools import wraps
from sqlite3 import Row
from typing import Any, ClassVar, ParamSpec, TypeVar

from flask import Response, abort
from typing_extensions import Protocol, Self
from werkzeug.datastructures import ImmutableMultiDict

from .auth import get_auth
from .db import get_db

# This module handles common class configuration (access control, LLM
# selection) and also provides a generic interface to manage
# application-specific class configuration.
#
# Any application can register a ContextConfig dataclass with this module using
# `register_context()` to add an application-specific section for contexts to
# the instructor class configuration form.  The application itself must provide
# a template for a context configuration set/update form (specified in the
# `template` attribute of the dataclass).  The class_config module handles that
# form's rendering (`context_form()`) and submission (`set_context()`).  The
# application itself must implement any other logic for using the contexts
# throughout the app.
#
# App-specific context configuration data are stored in dataclasses.  The
# dataclass must specify the template filename, define the config's fields and
# their types, and implement a `from_request_form()` class method that
# generates a config object based on inputs in request.form (as submitted from
# the form in the specified template).

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
    def from_request_form(cls, name: str, form: ImmutableMultiDict[str, str]) -> Self:
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


T = TypeVar('T', bound='ContextConfig')

def get_available_contexts(ctx_class: type[T]) -> dict[str, T]:
    db = get_db()
    auth = get_auth()

    class_id = auth['class_id']
    # TODO: filter by available using current date
    context_rows = db.execute("SELECT * FROM contexts WHERE class_id=?", [class_id]).fetchall()

    return {row['name']: ctx_class.from_row(row) for row in context_rows}


def get_context_config_by_id(ctx_class: type[T], ctx_id: int) -> T:
    assert _context_class is not None

    db = get_db()
    auth = get_auth()

    class_id = auth['class_id']  # just for extra safety: double-check that the context is in the current class

    context_row = db.execute("SELECT config FROM contexts WHERE class_id=? AND id=?", [class_id, ctx_id]).fetchone()
    return ctx_class.from_row(context_row)


def get_context_config_by_name(ctx_class: type[T], ctx_name: str) -> T:
    assert _context_class is not None

    db = get_db()
    auth = get_auth()

    class_id = auth['class_id']

    context_row = db.execute("SELECT config FROM contexts WHERE class_id=? AND name=?", [class_id, ctx_name]).fetchone()
    return ctx_class.from_row(context_row)
