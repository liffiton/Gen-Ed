from flask import Blueprint, render_template

from .auth import get_auth, login_required
from .db import get_db


bp = Blueprint('profile', __name__, url_prefix="/profile", template_folder='templates')


@bp.route("/")
@login_required
def main():
    db = get_db()
    auth = get_auth()
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

    class_id = auth['class_id'] or -1   # can't do a != to None/null, so convert that to -1 to match all classes in that case
    other_classes = db.execute("""
        SELECT
            classes.id,
            classes.name,
            roles.role
        FROM roles
        LEFT JOIN classes ON roles.class_id=classes.id
        WHERE roles.user_id=? AND roles.active=1 AND classes.id != ?
    """, [user_id, class_id]).fetchall()

    return render_template("profile_view.html", user=user, other_classes=other_classes)
