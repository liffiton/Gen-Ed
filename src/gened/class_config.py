import asyncio
import datetime as dt
import json
from dataclasses import Field, asdict
from sqlite3 import Row
from typing import Any, ClassVar, TypeVar

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)
from typing_extensions import Protocol, Self
from werkzeug.datastructures import ImmutableMultiDict
from werkzeug.wrappers.response import Response

from .auth import get_auth, instructor_required
from .db import get_db
from .openai import LLMDict, get_completion, get_models, with_llm
from .tz import date_is_past

bp = Blueprint('class_config', __name__, url_prefix="/instructor/config", template_folder='templates')


# This module handles common class configuration (access control, LLM
# selection) and also provides a generic interface to manage
# application-specific class configuration.
#
# Any application can register a ContextConfig dataclass with this module using
# `register_context()` to add an application-specific section to the
# instructor class configuration form.  The application itself must provide a
# template for a configuration set/update form (specified in the the `template`
# attribute of the dataclass).  This module handles that form's submission (in
# `set()`).  The application itself must implement any other logic for using
# the configuration throughout the app.
#
# App-specific class configuration data are stored in dataclasses.  The
# dataclass must specify the template filename, define the config's fields and
# their types, and implement a `from_request_form()` class method that
# generates a config object based on inputs in request.form.

# For type checking classes for storing a class configuration:
class ContextConfig(Protocol):
    # Must contain a template attribute with the name of a template file
    template: str
    # So it looks like a dataclass:
    __dataclass_fields__: ClassVar[dict[str, Field[Any]]]

    # Instantiate from a request form (must be implemented by application):
    @classmethod
    def from_request_form(cls, form: ImmutableMultiDict[str, str]) -> Self:
        ...

    # Instantiate from JSON (implemented here) (requires correct field names in JSON)
    @classmethod
    def from_json(cls, json_txt: str) -> Self:
        data = json.loads(json_txt)
        filtered = {key: data[key] for key in cls.__dataclass_fields__ if key in data and key != "template"}
        return cls(**filtered)

    # Dump config data (all but template name) to JSON (implemented here)
    def to_json(self) -> str:
        without_template = {k: v for k, v in asdict(self).items() if k != "template"}
        return json.dumps(without_template)


# Store a registered config class.
_context_class: type[ContextConfig] | None = None

def register_context(cls: type[ContextConfig]) -> type[ContextConfig]:
    """ Register a class configuration dataclass with this module.
    Used by each specific application that needs app-specific class configuration.
    May be used as a decorator (returns the given class unmodified).
    """
    global _context_class  # noqa: PLW0603 (global statement)
    _context_class = cls
    return cls


T = TypeVar('T', bound='ContextConfig')

def get_context(config_class: type[T]) -> T:
    if 'context' not in g:
        auth = get_auth()
        class_id = auth['class_id']

        if class_id is None:
            g.context = config_class()
        else:
            db = get_db()
            config_row = db.execute("SELECT config FROM classes WHERE id=?", [class_id]).fetchone()
            context_dict = json.loads(config_row['config'])
            g.context = config_class(**context_dict)

    return g.context  # type: ignore [no-any-return]


@bp.route("/")
@instructor_required
def config_form() -> str:
    db = get_db()
    auth = get_auth()

    class_id = auth['class_id']

    class_row = db.execute("""
        SELECT classes.id, classes.enabled, classes_user.link_ident, classes_user.link_reg_expires, classes_user.openai_key, classes_user.model_id
        FROM classes
        LEFT JOIN classes_user
          ON classes.id = classes_user.class_id
        WHERE classes.id=?
    """, [class_id]).fetchone()

    # TODO: refactor into function for checking start/end dates
    expiration_date = class_row['link_reg_expires']
    if expiration_date is None:
        link_reg_state = None  # not a user-created class
    elif date_is_past(expiration_date):
        link_reg_state = "disabled"
    elif expiration_date == dt.date.max:
        link_reg_state = "enabled"
    else:
        link_reg_state = "date"

    contexts = None
    if _context_class is not None:
        # get contexts
        contexts = db.execute("""
            SELECT contexts.*
            FROM contexts
            WHERE contexts.class_id=?
            ORDER BY contexts.class_order
        """, [class_id]).fetchall()

    return render_template("instructor_class_config.html", class_row=class_row, link_reg_state=link_reg_state, models=get_models(), contexts=contexts)


@bp.route("/test_llm")
@instructor_required
@with_llm()
def test_llm(llm_dict: LLMDict) -> Response | dict[str, Any]:
    response, response_txt = asyncio.run(get_completion(
        client=llm_dict['client'],
        model=llm_dict['model'],
        prompt="Please write 'OK'"
    ))

    if 'error' in response:
        return {'result': 'error', 'msg': 'Error!', 'error': f"<b>Error:</b><br>{response_txt}"}
    else:
        if response_txt != "OK":
            current_app.logger.error(f"LLM check had no error but responded not 'OK'?  Response: {response_txt}")
        return {'result': 'success', 'msg': 'Success!', 'error': None}


@bp.route("/context/<int:ctx_id>")
@instructor_required
def context_form(ctx_id: int) -> str | Response:
    if _context_class is None:
        # only if a context class has been registered
        return abort(404)

    db = get_db()
    auth = get_auth()

    # if a context id is specified, show form for editing a single context
    context = db.execute("SELECT * FROM contexts WHERE id=?", [ctx_id]).fetchone()

    # verify the current user can edit this context
    class_id = auth['class_id']
    if context['class_id'] != class_id:
        return abort(403)

    context_config = _context_class.from_json(context['config'])

    return render_template(context_config.template, context=context, context_config=context_config)


@bp.route("/context/set/<int:ctx_id>", methods=["POST"])
@instructor_required
def set_context(ctx_id: int) -> Response:
    if _context_class is None:
        # only if a context class has been registered
        return abort(404)

    db = get_db()
    auth = get_auth()

    # verify the current user can edit this context
    class_id = auth['class_id']
    context = db.execute("SELECT * FROM contexts WHERE id=?", [ctx_id]).fetchone()
    if context['class_id'] != class_id:
        return abort(403)

    context_json = _context_class.from_request_form(request.form).to_json()

    db.execute("UPDATE contexts SET config=? WHERE id=?", [context_json, ctx_id])
    db.commit()

    flash(f"Configuration for context '{context['name']}' set!", "success")
    return redirect(url_for(".config_form"))
