# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from sqlite3 import Row
from typing import Any, Self

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
from jinja2 import Template
from werkzeug.datastructures import ImmutableMultiDict
from werkzeug.wrappers.response import Response

from gened.auth import get_auth, get_auth_class, instructor_required
from gened.db import get_db

from .extra_sections import register_extra_section

# This module provides the basis for application-specific configuration tables,
# in which multiple elements of a given type need to be managed in a table.
#
# It is kept relatively generic, and much of the specific implementation of the
# configured items can be controlled by the provided dataclass and related
# templates.
#
# App-specific configuration data are stored in dataclasses.  The dataclass
# must specify the item's name, define the config's fields and their types, and
# implement the `from_request_form()` class method that creates a new object
# based on inputs in request.form (as submitted from the form in the specified
# template).


@dataclass
class ConfigItem(ABC):
    """ Abstract base class for defining types of configuration items to be
    managed in a ConfigTable.
    """
    name: str
    row_id: int | None = None

    @classmethod
    def initial(cls) -> Self | None:
        """ Return an "initial" object for this class.
        Can be overridden, e.g., if using a cache.
        """
        return None

    @classmethod
    @abstractmethod
    def from_request_form(cls, form: ImmutableMultiDict[str, str]) -> Self:
        ...

    @classmethod
    def from_row(cls, row: Row) -> Self:
        """ Instantiate an item object from an SQLite row.
            (Requires correct field names in the row and in its 'config' JSON column.)
        """
        attrs = json.loads(row['config'])
        attrs['name'] = row['name']
        attrs['row_id'] = row['id']
        return cls(**attrs)

    def to_json(self) -> str:
        """ Dump config data (all but name and row_id) to JSON (implemented here) """
        filtered_attrs = {k: v for k, v in asdict(self).items() if k not in ('name', 'row_id')}
        return json.dumps(filtered_attrs)

@dataclass(frozen=True, kw_only=True)
class ConfigTable:
    name: str
    requires_experiment: str | None = None
    config_item_class: type[ConfigItem]
    db_table_name: str
    display_name: str
    display_name_plural: str
    help_text: Template | str | None = None
    edit_form_template: str
    routes: Blueprint | None = None

    @property
    def edit_url(self) -> str:
        return url_for('class_config.class_config_table.edit_item_form', table_name=self.name)

    @property
    def new_url(self) -> str:
        return url_for('class_config.class_config_table.new_item_form', table_name=self.name)


_registered_tables: dict[str, ConfigTable] = {}

class DuplicateTableError(Exception):
    def __init__(self, name: str):
        super().__init__(f"A table named {name} has already been registered")

def register_config_table(table: ConfigTable) -> None:
    """ Register the configuration UI as an extra config section. """
    if table.name in _registered_tables:
        raise DuplicateTableError(table.name)

    _registered_tables[table.name] = table

    def get_data() -> dict[str, Any]:
        return _get_item_config_data(db_table = table.db_table_name)

    if table.routes is not None:
        bp.register_blueprint(table.routes)

    register_extra_section(
        "config_table_fragment.html",
        get_data,
        extra_args={'table': table},
        requires_experiment=table.requires_experiment,
    )


def _get_instructor_courses(user_id: int, current_class_id: int, db_table: str) -> list[dict[str, str | list[str]]]:
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

    # Fetch items for each eligible course to display in the copy modal
    instructor_courses_data = []
    for course in course_rows:
        course_items = db.execute(f"""
            SELECT name FROM {db_table} WHERE class_id = ? ORDER BY class_order
        """, [course['id']]).fetchall()
        instructor_courses_data.append({
            'id': course['id'],
            'name': course['name'],
            'items': [item['name'] for item in course_items]
        })

    return instructor_courses_data


def _get_item_config_data(db_table: str) -> dict[str, Any]:
    db = get_db()
    auth = get_auth()
    cur_class = get_auth_class()
    class_id = cur_class.class_id

    items = db.execute(f"""
        SELECT id, name, CAST(available AS TEXT) AS available
        FROM {db_table}
        WHERE class_id=?
        ORDER BY class_order
    """, [class_id]).fetchall()
    items = [dict(c) for c in items]  # for conversion to json

    assert auth.user
    copyable_courses = _get_instructor_courses(auth.user.id, class_id, db_table)

    return {"item_data": items, "copyable_courses": copyable_courses}


### Blueprint + routes
bp = Blueprint('class_config_table', __name__, url_prefix="/table/<string:table_name>", template_folder='templates')

@bp.url_value_preprocessor
def pull_table_name(_endpoint: str | None, values: dict[str, Any] | None) -> None:
    """ Pull the table_name from the parsed URL parameters, validate that the
    path specified a registered table (abort 404 if not), and make the table
    config object available in g instead.
    """
    if values is None:
        return
    table_name = values.pop('table_name')
    if table_name not in _registered_tables:
        abort(404)
    g.config_table = _registered_tables[table_name]

@bp.url_value_preprocessor
def check_valid_item(_endpoint: str | None, values: dict[str, Any] | None) -> None:
    """
    For any endpoints that require an item_id in the path, check that the
    specified item is valid in the current class, aborting with a 403 if not.

    When used with @instructor_required, in which case this guarantees the
    current user is allowed to edit the specified item.

    Pops the 'item_id' argument and replaces it with an 'item' named argument
    carrying a ConfigItem built from the item's db row.
    """
    if values is None or 'item_id' not in values:
        return

    db = get_db()
    auth = get_auth()
    if not auth.cur_class:
        return

    cur_class = auth.cur_class

    # verify the given item is in the user's current class
    cur_class_id = cur_class.class_id
    item_id = values.pop('item_id')
    query = f"SELECT * FROM {g.config_table.db_table_name} WHERE id=?"
    item_row = db.execute(query, [item_id]).fetchone()
    if item_row['class_id'] != cur_class_id:
        abort(403)

    values['item'] = g.config_table.config_item_class.from_row(item_row)

@bp.url_defaults
def add_table_name(_endpoint: str, values: dict[str, Any]) -> None:
    """ Make any url_for into this blueprint use the current request context's table_name by default. """
    if 'config_table' in g:
        values.setdefault('table_name', g.config_table.name)

@bp.before_request
@instructor_required
def before_request() -> None:
    """ Apply instructor_required decorator to protect all class_config blueprint endpoints. """


@bp.route("/edit/", methods=[])  # just for url_for() in js code
@bp.route("/edit/<int:item_id>")
def edit_item_form(item: ConfigItem) -> str | Response:
    return render_template(g.config_table.edit_form_template, item=item)


@bp.route("/new")
def new_item_form() -> str | Response:
    return render_template(g.config_table.edit_form_template, item=g.config_table.config_item_class.initial())


@bp.route("/create", methods=["POST"])
def create_item() -> Response:
    cur_class = get_auth_class()
    item = g.config_table.config_item_class.from_request_form(request.form)
    _insert_item(cur_class.class_id, item.name, item.to_json(), "9999-12-31")  # defaults to hidden
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
        current_app.logger.warning(f"User {auth.user.id} attempted to copy items from class {source_class_id} without instructor role.")
        abort(403) # User is not instructor in source course
    # --- End Security Check ---

    query = f"SELECT * FROM {g.config_table.db_table_name} WHERE class_id = ? ORDER BY class_order"
    source_items = db.execute(query, [source_class_id]).fetchall()
    source_class_name = db.execute("SELECT name FROM classes WHERE id = ?", [source_class_id]).fetchone()['name']

    if not source_items:
        flash(f"Course '{source_class_name}' has no items to copy.", "warning")
        return redirect(url_for("class_config.config_form"))

    for item_row in source_items:
        _insert_item(target_class_id, item_row['name'], item_row['config'], "9999-12-31")  # default to hidden

    flash(f"Successfully copied {len(source_items)} item(s) from '{source_class_name}'.", "success")

    return redirect(url_for("class_config.config_form"))


@bp.route("/copy/", methods=[])  # just for url_for() in js code
@bp.route("/copy/<int:item_id>", methods=["POST"])
def copy_item(item: ConfigItem) -> Response:
    cur_class = get_auth_class()

    # passing existing name, but _insert_item will take care of finding
    # a new, unused name in the class.
    _insert_item(cur_class.class_id, item.name, item.to_json(), "9999-12-31")  # default to hidden
    return redirect(url_for("class_config.config_form"))


def _make_unique_item_name(db_table_name: str, class_id: int, name: str, item_id: int|None = None) -> str:
    """ Given a class and a potential item name, return an item name that
        is unique within that class.

        (Yes, there's a race condition when using this.  Worst-case, the
        database constraints will error out an invalid insert or update.)

        If item_id is provided, then allow the name to match that row's existing
        name.  (Used in an update, where the new name just can't match any
        *other* row's names.)
    """
    db = get_db()

    new_name = name
    i = 0

    if item_id is None:
        item_id = -1  # so the != check works correctly in the SQL
                      # if item_id is -1, then the id!= constraint will
                      # always be True.

    def name_exists(candidate: str) -> bool:
        """ Return True if the candidate name exists in the table already, False otherwise. """
        row = db.execute(f"SELECT id FROM {db_table_name} WHERE class_id=? AND name=? AND id!=?", [class_id, candidate, item_id]).fetchone()
        return row is not None

    while name_exists(new_name):
        i += 1
        new_name = f"{name} ({i})"

    return new_name


def _insert_item(class_id: int, name: str, config: str, available: str) -> int:
    db = get_db()

    # names must be unique within a class: check/look for an unused name
    new_name = _make_unique_item_name(g.config_table.db_table_name, class_id, name)

    cur = db.execute(f"""
        INSERT INTO {g.config_table.db_table_name} (class_id, name, config, available, class_order)
        VALUES (?, ?, ?, ?, (SELECT COALESCE(MAX(class_order)+1, 0) FROM {g.config_table.db_table_name} WHERE class_id=?))
    """, [class_id, new_name, config, available, class_id])
    db.commit()
    new_item_id = cur.lastrowid
    assert new_item_id is not None

    flash(f"Item '{new_name}' created.", "success")

    return new_item_id


@bp.route("/update/<int:item_id>", methods=["POST"])
def update_item(item: ConfigItem) -> Response:
    db = get_db()

    # names must be unique within a class: check/look for an unused name
    cur_class = get_auth_class()
    new_item = g.config_table.config_item_class.from_request_form(request.form)
    new_name = _make_unique_item_name(g.config_table.db_table_name, cur_class.class_id, request.form['name'], item.row_id)

    db.execute(f"UPDATE {g.config_table.db_table_name} SET name=?, config=? WHERE id=?", [new_name, new_item.to_json(), item.row_id])
    db.commit()

    flash(f"Configuration for item '{item.name}' updated.", "success")
    return redirect(url_for("class_config.config_form"))


@bp.route("/delete/", methods=[])  # just for url_for() in js code
@bp.route("/delete/<int:item_id>", methods=["POST"])
def delete_item(item: ConfigItem) -> Response:
    db = get_db()

    db.execute(f"DELETE FROM {g.config_table.db_table_name} WHERE id=?", [item.row_id])
    db.commit()

    flash(f"Item '{item.name}' deleted.", "success")
    return redirect(url_for("class_config.config_form"))


@bp.route("/update_order", methods=["POST"])
def update_order() -> str:
    db = get_db()
    cur_class = get_auth_class()

    class_id = cur_class.class_id  # Get the current class to ensure we don't change another class.

    ordered_ids = request.json
    assert isinstance(ordered_ids, list)
    sql_tuples = [(i, item_id, class_id) for i, item_id in enumerate(ordered_ids)]

    # Check class_id in the WHERE to prevent changing items in another class
    db.executemany(f"UPDATE {g.config_table.db_table_name} SET class_order=? WHERE id=? AND class_id=?", sql_tuples)
    db.commit()

    return 'ok'


@bp.route("/update_available", methods=["POST"])
def update_available() -> str:
    db = get_db()
    cur_class = get_auth_class()

    class_id = cur_class.class_id  # Get the current class to ensure we don't change another class.

    data = request.json
    assert isinstance(data, dict)

    # Check class_id in the WHERE to prevent changing items in another class
    db.execute(f"UPDATE {g.config_table.db_table_name} SET available=? WHERE id=? AND class_id=?", [data['available'], data['item_id'], class_id])
    db.commit()

    return 'ok'
