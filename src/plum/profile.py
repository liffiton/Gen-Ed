from flask import Blueprint, redirect, render_template, url_for

from .auth import get_session_auth, login_required, set_session_auth_class
from .db import get_db


bp = Blueprint('profile', __name__, url_prefix="/profile", template_folder='templates')


@bp.route("/")
@login_required
def main():
    db = get_db()
    auth = get_session_auth()
    user_id = auth['user_id']
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

    class_id = auth['class_id']
    other_classes = db.execute("""
        SELECT
            classes.id,
            classes.name,
            roles.role
        FROM roles
        LEFT JOIN classes ON roles.class_id=classes.id
        WHERE roles.user_id=? AND classes.id <> ?
    """, [user_id, class_id]).fetchall()

    return render_template("profile_view.html", user=user, other_classes=other_classes)


@bp.route("/switch_class/<int:class_id>")
@login_required
def switch_class(class_id):
    auth = get_session_auth()
    user_id = auth['user_id']

    db = get_db()
    row = db.execute("""
        SELECT
            roles.id AS role_id,
            roles.role,
            classes.id AS class_id,
            classes.name AS class_name
        FROM roles
        LEFT JOIN classes ON roles.class_id=classes.id
        WHERE roles.user_id=? AND classes.id=?
    """, [user_id, class_id]).fetchone()

    set_session_auth_class(row['class_id'], row['class_name'], row['role_id'], row['role'])

    return redirect(url_for(".main"))
