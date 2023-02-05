from flask import Blueprint, render_template, request

from .db import get_db
from .auth import get_session_auth, instructor_required


bp = Blueprint('instructor', __name__, url_prefix="/instructor", template_folder='templates')


@bp.route("/")
@instructor_required
def main():
    db = get_db()
    auth = get_session_auth()

    class_id = auth['role']['class_id']

    users = db.execute("SELECT users.*, COUNT(queries.id) AS num_queries FROM users LEFT JOIN queries ON users.id=queries.user_id JOIN roles ON users.id=roles.user_id WHERE roles.class_id=? GROUP BY users.id", [class_id]).fetchall()

    username = None
    if 'username' in request.args:
        username = request.args['username']
        queries = db.execute("SELECT queries.*, users.username FROM queries JOIN users ON queries.user_id=users.id JOIN roles ON queries.role_id=roles.id WHERE users.username=? AND roles.class_id=? ORDER BY query_time DESC", [username, class_id]).fetchall()
    else:
        queries = db.execute("SELECT queries.*, users.username FROM queries JOIN users ON queries.user_id=users.id JOIN roles ON queries.role_id=roles.id WHERE roles.class_id=? ORDER BY query_time DESC", [auth['role']['class_id']]).fetchall()

    return render_template("instructor.html", users=users, queries=queries, username=username)
