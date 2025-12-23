# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from dataclasses import replace

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.wrappers.response import Response

from .access import Access, control_blueprint_access
from .auth import generate_anon_username, get_auth
from .component_registry import get_component_data_source_by_name, get_registered_components
from .csv import csv_response
from .data_deletion import delete_user_data
from .db import get_db
from .redir import safe_redirect
from .tables import Action, Col, DataTable, DataTableSpec, NumCol

bp = Blueprint('profile', __name__, template_folder='templates')

# Require login for all blueprint routes
control_blueprint_access(bp, Access.LOGIN)


@bp.route("/")
def main() -> str:
    db = get_db()
    auth = get_auth()
    user_id = auth.user_id
    assert user_id is not None

    user_row = db.execute("""
        SELECT
            users.*,
            auth_providers.name AS provider_name
        FROM users
        LEFT JOIN auth_providers ON auth_providers.id=users.auth_provider
        WHERE users.id=?
    """, [user_id]).fetchone()

    data_sources = [ c.data_source for c in get_registered_components() if c.data_source ]
    data_counts = {
        ds.table_spec.name: ds.get_user_counts(user_id)
        for ds in data_sources
    }

    cur_class_id = auth.cur_class.class_id if auth.cur_class else -1   # can't do a != to None/null in SQL, so convert that to -1 to match all classes in that case
    other_classes = db.execute("""
        SELECT
            classes.id,
            classes.name,
            roles.role
        FROM roles
        LEFT JOIN classes ON roles.class_id=classes.id
        WHERE roles.user_id=?
          AND roles.active=1
          AND classes.id != ?
          AND classes.enabled=1
        ORDER BY classes.id DESC
    """, [user_id, cur_class_id]).fetchall()

    archived_classes = db.execute("""
        SELECT
            classes.id,
            classes.name,
            roles.role
        FROM roles
        LEFT JOIN classes ON roles.class_id=classes.id
        WHERE roles.user_id=?
          AND roles.active=1
          AND classes.id != ?
          AND classes.enabled=0
        ORDER BY classes.id DESC
    """, [user_id, cur_class_id]).fetchall()

    # Get any classes created by this user
    created_classes = db.execute("""
        SELECT classes.name
        FROM classes_user
        JOIN classes ON classes_user.class_id = classes.id
        WHERE creator_user_id = ?
    """, [user_id]).fetchall()

    models = db.execute("""
        SELECT
            id,
            shortname AS name,
            custom_endpoint AS endpoint,
            model,
            (SELECT COUNT(*) FROM classes_user AS cu WHERE cu.model_id=models.id) AS "used in #classes"
        FROM models
        WHERE owner_id = ?
    """, [user_id]).fetchall()

    table_spec = DataTableSpec(
        name='models',
        columns=[
            NumCol('id', hidden=True),
            Col('name'),
            Col('endpoint'),
            Col('model'),
            NumCol('used in #classes'),
        ],
        link_col=0,
        link_template='/models/edit/${value}',
        actions=[
            Action("Edit model", icon='pencil', url=url_for('models.models_edit'), id_col=0),
        ],
    )
    models_table = DataTable(spec=table_spec, data=models)

    return render_template(
        "profile_view.html",
        user=user_row,
        data_counts=data_counts,
        other_classes=other_classes,
        archived_classes=archived_classes,
        created_classes=created_classes,
        models_table=models_table
    )


@bp.route("/data/")
def view_data() -> str:
    tables = []
    for component in get_registered_components():
        if not (ds := component.data_source):
            continue

        data = ds.get_user_data(limit=-1)  # -1 = no limit
        if len(data) == 0:
            # don't show tables with no data
            continue

        table_spec = ds.table_spec
        table_spec = replace(table_spec, csv_link = url_for(".get_csv", kind=table_spec.name))
        table_spec = table_spec.with_hidden('user')  # it's just the current user's data; no need to list them in every row
        table = DataTable(spec=table_spec, data=data)
        tables.append((ds.display_name, table))

    return render_template("profile_view_data.html", tables=tables)


@bp.route("/data/csv/<string:kind>")
def get_csv(kind: str) -> str | Response:
    data_source = get_component_data_source_by_name(kind)
    if data_source is None:
        abort(404)

    auth = get_auth()
    assert auth.user

    queries = data_source.get_user_data(limit=-1)  # -1 = no limit
    return csv_response(auth.user.display_name, kind, queries)


@bp.route("/delete_data", methods=['POST'])
def delete_data() -> Response:
    # Require explicit confirmation
    if request.form.get('confirm_delete') != 'DELETE':
        flash("Data deletion requires confirmation. Please type DELETE to confirm.", "warning")
        return safe_redirect(request.referrer, default_endpoint="profile.main")

    auth = get_auth()
    user_id = auth.user_id
    assert user_id is not None  # due to @login_required
    db = get_db()

    # Check if user has any classes they created
    created_classes = db.execute("""
        SELECT classes.name
        FROM classes_user
        JOIN classes ON classes_user.class_id = classes.id
        WHERE creator_user_id = ?
    """, [user_id]).fetchall()

    if created_classes:
        class_names = ", ".join(row['name'] for row in created_classes)
        flash(f"You must delete all classes you created before deleting your data. Please delete these classes first: {class_names}", "danger")
        return safe_redirect(request.referrer, default_endpoint="profile.main")

    delete_user_data(user_id)

    # Clear their session to log them out
    session.clear()

    current_app.logger.info(f"Account deleted: ID {user_id}")
    flash("Your data has been deleted and your account has been deactivated.", "success")
    return redirect(url_for("auth.login"))


@bp.route("/anonymize", methods=['POST'])
def anonymize() -> Response:
    auth = get_auth()
    user_id = auth.user_id
    assert user_id is not None  # due to @login_required
    db = get_db()

    # Check if this is an external, non-LTI account
    auth_row = db.execute("""
        SELECT auth_external.user_id, auth_providers.name as provider
        FROM auth_external
        JOIN auth_providers ON auth_providers.id = auth_external.auth_provider
        WHERE user_id=?
    """, [user_id]).fetchone()

    if not auth_row or auth_row['provider'] == 'lti':
        flash("Account anonymization is only available to external, non-LTI accounts.", "warning")
        return safe_redirect(request.referrer, default_endpoint="profile.main")

    # Generate new anonymous display name
    new_name = generate_anon_username()

    # Update user record to remove personal info
    db.execute("""
        UPDATE users
        SET full_name = ?,
            email = NULL,
            auth_name = NULL
        WHERE id = ?
    """, [new_name, user_id])

    # Mark external auth entry as anonymous
    db.execute("""
        UPDATE auth_external
        SET is_anon = 1
        WHERE user_id = ?
    """, [user_id])

    db.commit()

    current_app.logger.info(f"Account anonymized: ID {user_id}")
    flash("Your account has been anonymized.", "success")
    return redirect(url_for("profile.main"))
