# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.wrappers.response import Response

from .auth import get_auth, login_required
from .data_deletion import delete_user_data
from .db import get_db
from .redir import safe_redirect

bp = Blueprint('profile', __name__, url_prefix="/profile", template_folder='templates')


@bp.route("/")
@login_required
def main() -> str:
    db = get_db()
    auth = get_auth()
    user_id = auth.user_id
    user = db.execute("""
        SELECT
            users.*,
            auth_providers.name AS provider_name,
            COUNT(queries.id) AS num_queries,
            SUM(CASE WHEN queries.query_time > date('now', '-7 days') THEN 1 ELSE 0 END) AS num_recent_queries
        FROM users
        LEFT JOIN queries ON queries.user_id=users.id
        LEFT JOIN auth_providers ON auth_providers.id=users.auth_provider
        WHERE users.id=?
    """, [user_id]).fetchone()

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

    return render_template(
        "profile_view.html",
        user=user,
        other_classes=other_classes,
        archived_classes=archived_classes,
        created_classes=created_classes
    )


@bp.route("/delete_data", methods=['POST'])
@login_required
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

    # Call application-specific data deletion handler(s)
    delete_user_data(user_id)

    # Deactivate all roles
    db.execute("UPDATE roles SET user_id = -1, active = 0 WHERE user_id = ?", [user_id])

    # Anonymize and deactivate user account
    db.execute("""
        UPDATE users
        SET full_name = '[deleted]',
            email = '[deleted]',
            auth_name = '[deleted]',
            last_class_id = NULL,
            query_tokens = 0
        WHERE id = ?
    """, [user_id])

    # Remove auth entries
    db.execute("DELETE FROM auth_local WHERE user_id = ?", [user_id])
    db.execute("DELETE FROM auth_external WHERE user_id = ?", [user_id])

    db.commit()

    # Clear their session and log them out
    session.clear()
    flash("Your data has been deleted and your account has been deactivated.", "success")
    return redirect(url_for("auth.login"))
