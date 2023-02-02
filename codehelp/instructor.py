from flask import Blueprint, render_template, request

from .db import get_db
from .auth import get_session_auth, instructor_required


bp = Blueprint('instructor', __name__, url_prefix="/instructor", template_folder='templates')


@bp.route("/")
@instructor_required
def main():
    db = get_db()
    auth = get_session_auth()

    lti_context = auth['role']['context']

    users = db.execute("SELECT users.*, COUNT(queries.id) AS num_queries FROM users LEFT JOIN queries ON users.id=queries.user_id JOIN roles ON users.id=roles.user_id WHERE roles.lti_context=? GROUP BY users.id", [lti_context]).fetchall()

    username = None
    if 'username' in request.args:
        username = request.args['username']
        queries = db.execute("SELECT queries.*, users.username FROM queries JOIN users ON queries.user_id=users.id JOIN roles ON queries.role_id=roles.id WHERE users.username=? AND roles.lti_context=? ORDER BY query_time DESC", [username, lti_context]).fetchall()
    else:
        queries = db.execute("SELECT queries.*, users.username FROM queries JOIN users ON queries.user_id=users.id JOIN roles ON queries.role_id=roles.id WHERE roles.lti_context=? ORDER BY query_time DESC", [auth['role']['context']]).fetchall()

    return render_template("instructor.html", users=users, queries=queries, username=username)
