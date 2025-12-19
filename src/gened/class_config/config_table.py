# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from typing import Any

from flask import (
    Blueprint,
    Flask,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.wrappers.response import Response

from gened.auth import get_auth, get_auth_class
from gened.db import get_db

from .types import ConfigItem


def create_blueprint(app: Flask) -> Blueprint:
    bp = create_base_blueprint()
    bp.register_blueprint(crud_bp)

    for table in app.extensions['gen_ed_config_tables'].values():
        if table.extra_routes is not None:
            bp.register_blueprint(table.extra_routes)

    return bp


def create_base_blueprint() -> Blueprint:
    bp = Blueprint('table', __name__, url_prefix="/table/<string:table_name>", template_folder='templates')

    @bp.url_value_preprocessor
    def pull_table_name(_endpoint: str | None, values: dict[str, Any] | None) -> None:
        """ Pull the table_name from the parsed URL parameters, validate that the
        path specified a registered table (abort 404 if not), and make the table
        config object available in g instead.
        """
        if values is None:
            return
        table_name = values.pop('table_name')
        registered_tables = current_app.extensions['gen_ed_config_tables']
        if table_name not in registered_tables:
            abort(404)
        g.config_table = registered_tables[table_name]

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

    return bp


crud_bp = Blueprint('crud', __name__, template_folder='templates')

@crud_bp.route("/edit/", methods=[])  # just for url_for() in js code
@crud_bp.route("/edit/<int:item_id>")
def edit_item_form(item: ConfigItem) -> str | Response:
    return render_template(g.config_table.edit_form_template, item=item)


@crud_bp.route("/new")
def new_item_form() -> str | Response:
    return render_template(g.config_table.edit_form_template, item=g.config_table.config_item_class.initial())


@crud_bp.route("/create", methods=["POST"])
def create_item() -> Response:
    cur_class = get_auth_class()
    item = g.config_table.config_item_class.from_request_form(request.form)
    _, name = _insert_item(cur_class.class_id, item.name, item.to_json(), "9999-12-31")  # defaults to hidden
    flash(f"Item '{name}' created.", "success")
    return redirect(url_for("class_config.base.config_form"))


@crud_bp.route("/copy_from_course", methods=["POST"])
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
        return redirect(url_for("class_config.base.config_form"))

    for item_row in source_items:
        _insert_item(target_class_id, item_row['name'], item_row['config'], "9999-12-31")  # default to hidden

    flash(f"Successfully copied {len(source_items)} item(s) from '{source_class_name}'.", "success")

    return redirect(url_for("class_config.base.config_form"))


@crud_bp.route("/copy/", methods=[])  # just for url_for() in js code
@crud_bp.route("/copy/<int:item_id>", methods=["POST"])
def copy_item(item: ConfigItem) -> Response:
    cur_class = get_auth_class()

    # passing existing name, but _insert_item will take care of finding
    # a new, unused name in the class.
    _, new_name = _insert_item(cur_class.class_id, item.name, item.to_json(), "9999-12-31")  # default to hidden
    flash(f"Item '{item.name}' copied to '{new_name}'.", "success")
    return redirect(url_for("class_config.base.config_form"))


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


def _insert_item(class_id: int, name: str, config: str, available: str) -> tuple[int, str]:
    """ Insert an item with the given name, config, and availability into the given class.
    Ensures the name is unique within the class, modifying it as needed.
    Returns a tuple of the new row id and the name of the newly inserted item.
    """
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
    return new_item_id, new_name


@crud_bp.route("/update/<int:item_id>", methods=["POST"])
def update_item(item: ConfigItem) -> Response:
    db = get_db()

    # names must be unique within a class: check/look for an unused name
    cur_class = get_auth_class()
    new_item = g.config_table.config_item_class.from_request_form(request.form)
    new_name = _make_unique_item_name(g.config_table.db_table_name, cur_class.class_id, request.form['name'], item.row_id)

    db.execute(f"UPDATE {g.config_table.db_table_name} SET name=?, config=? WHERE id=?", [new_name, new_item.to_json(), item.row_id])
    db.commit()

    flash(f"Configuration for item '{item.name}' updated.", "success")
    return redirect(url_for("class_config.base.config_form"))


@crud_bp.route("/delete/", methods=[])  # just for url_for() in js code
@crud_bp.route("/delete/<int:item_id>", methods=["POST"])
def delete_item(item: ConfigItem) -> Response:
    db = get_db()

    db.execute(f"DELETE FROM {g.config_table.db_table_name} WHERE id=?", [item.row_id])
    db.commit()

    flash(f"Item '{item.name}' deleted.", "success")
    return redirect(url_for("class_config.base.config_form"))


@crud_bp.route("/update_order", methods=["POST"])
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


@crud_bp.route("/update_available", methods=["POST"])
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
