# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import datetime as dt
from typing import Any

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    render_template,
    request,
    url_for,
)
from werkzeug.wrappers.response import Response

from gened.access import instructor_required
from gened.auth import get_auth, get_auth_class
from gened.components import get_registered_components
from gened.db import get_db
from gened.llm import LLM, get_models, with_llm
from gened.redir import safe_redirect
from gened.tz import date_is_past

from .config_table import create_blueprint
from .types import ConfigTable

bp = Blueprint('base', __name__, template_folder='templates')


def build_blueprint() -> Blueprint:
    """ Build a new blueprint for class_config.
    We must create a new blueprint here so that we aren't trying to register
    new routes on a global blueprint object, which will fail during testing (as
    this will be called numerous times across the tests).
    """
    new_bp = Blueprint('class_config', __name__, template_folder='templates')

    # Apply instructor_required to protect all class_config blueprint endpoints.
    new_bp.before_request(instructor_required(lambda: None))

    new_bp.register_blueprint(bp)

    config_table_bp = create_blueprint()
    new_bp.register_blueprint(config_table_bp)

    return new_bp


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


def get_table_template_context(table: ConfigTable) -> dict[str, Any]:
    """ Returns a dictionary of context variables to be used within the config screen template. """
    db = get_db()
    auth = get_auth()
    cur_class = get_auth_class()
    class_id = cur_class.class_id

    items = db.execute(f"""
        SELECT id, name, CAST(available AS TEXT) AS available
        FROM {table.db_table_name}
        WHERE class_id=?
        ORDER BY class_order
    """, [class_id]).fetchall()
    items = [dict(c) for c in items]  # for conversion to json

    # add pre-generated URLs for actions and share links
    # (done here b/c it's awkward to do this in the template with some info from Jinja and some from JS)
    for item in items:
        item['url_edit'] = url_for('class_config.table.crud.edit_item_form', table_name=table.name, item_id=item['id'])
        item['url_copy'] = url_for('class_config.table.crud.copy_item', table_name=table.name, item_id=item['id'])
        item['url_delete'] = url_for('class_config.table.crud.delete_item', table_name=table.name, item_id=item['id'])
        item['share_links'] = []
        for share_link in table.share_links:
            if share_link.requires_experiment is None or share_link.requires_experiment in auth.class_experiments:
                item['share_links'].append({
                    'url': share_link.render_url(item),
                    'label': share_link.label}
                )

    assert auth.user
    copyable_courses = _get_instructor_courses(auth.user.id, class_id, table.db_table_name)

    return {
        "table": table,
        "item_data": items,
        "copyable_courses": copyable_courses
    }


@bp.route("/")
def config_form() -> str:
    db = get_db()

    cur_class = get_auth_class()
    class_id = cur_class.class_id

    class_row = db.execute("""
        SELECT classes.id, classes.enabled, classes_user.link_ident, classes_user.link_reg_expires, classes_user.link_anon_login, classes_user.llm_api_key, classes_user.model_id
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

    # Add config sections for registered components
    extra_sections_data = []
    for component in get_registered_components():
        if not (config_table := component.config_table):
            continue
        if not component.is_available():
            continue

        extra_section = {
            'template_name': 'config_table_fragment.html',
            'ctx': get_table_template_context(config_table),
        }
        extra_sections_data.append(extra_section)

    models = get_models(plus_id=class_row['model_id'])

    return render_template("instructor_class_config.html", class_row=class_row, link_reg_state=link_reg_state, user_is_creator=cur_class.user_is_creator, models=models, extra_sections_data=extra_sections_data)


@bp.route("/save/access", methods=["POST"])
def save_access_config() -> Response:
    db = get_db()

    # only trust class_id from auth, not from user
    cur_class = get_auth_class()
    class_id = cur_class.class_id

    if 'is_user_class' in request.form:
        # only present for user classes, not LTI
        link_reg_active = request.form['link_reg_active']
        if link_reg_active == "disabled":
            new_date = str(dt.date.min)
        elif link_reg_active == "enabled":
            new_date = str(dt.date.max)
        else:
            new_date = request.form['link_reg_expires']

        class_link_anon_login = 1 if 'class_link_anon_login' in request.form else 0
        db.execute("UPDATE classes_user SET link_reg_expires=?, link_anon_login=? WHERE class_id=?", [new_date, class_link_anon_login, class_id])

    class_enabled = 1 if 'class_enabled' in request.form else 0
    db.execute("UPDATE classes SET enabled=? WHERE id=?", [class_enabled, class_id])
    db.commit()
    flash("Class access configuration updated.", "success")

    return safe_redirect(request.referrer, default_endpoint="profile.main")

@bp.route("/save/llm", methods=["POST"])
def save_llm_config() -> Response:
    db = get_db()

    # only trust class_id from auth, not from user
    cur_class = get_auth_class()
    class_id = cur_class.class_id

    # only class creators can edit LLM config
    if not cur_class.user_is_creator:
        abort(403)

    if 'clear_llm_api_key' in request.form:
        db.execute("UPDATE classes_user SET llm_api_key='' WHERE class_id=?", [class_id])
        db.commit()
        flash("Class API key cleared.", "success")

    elif 'save_llm_form' in request.form:
        # validate specified model
        model_id = int(request.form['model_id'])
        valid_models = get_models()
        if not any(model_id == m['id'] for m in valid_models):
            flash("Invalid model.", "danger")
            return safe_redirect(request.referrer, default_endpoint="profile.main")

        if 'llm_api_key' in request.form:
            db.execute("UPDATE classes_user SET llm_api_key=? WHERE class_id=?", [request.form['llm_api_key'], class_id])
        db.execute("UPDATE classes_user SET model_id=? WHERE class_id=?", [model_id, class_id])
        db.commit()
        flash("Class language model configuration updated.", "success")

    return safe_redirect(request.referrer, default_endpoint="profile.main")


@bp.route("/test_llm")
@with_llm()
def test_llm(llm: LLM) -> str:
    response, response_txt = asyncio.run(llm.get_completion(prompt="Please write 'OK'"))

    if 'error' in response:
        return f"<b>Error:</b><br>{response_txt}"
    else:
        if response_txt != "OK":
            current_app.logger.error(f"LLM check had no error but responded not 'OK'?  Response: {response_txt}")
        return "ok"


@bp.route("/lti_content_select")
def lti_content_select() -> str:
    content_item_return_url = request.args.get('content_item_return_url')
    return render_template("lti_content_select.html", return_url=content_item_return_url)
