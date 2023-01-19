from flask import Blueprint, render_template, request

from .db import get_db
from .auth import admin_required


bp = Blueprint('admin', __name__, url_prefix="/admin", template_folder='templates')


@bp.route("/")
@admin_required
def main():
    db = get_db()
    users = db.execute("SELECT users.*, COUNT(queries.id) AS num_queries FROM users LEFT JOIN queries ON users.id=queries.user_id GROUP BY users.id").fetchall()

    username = None
    if 'username' in request.args:
        username = request.args['username']
        queries = db.execute("SELECT queries.*, users.username FROM queries JOIN users ON queries.user_id=users.id WHERE users.username=? ORDER BY query_time DESC", [username]).fetchall()
    else:
        queries = db.execute("SELECT queries.*, users.username FROM queries JOIN users ON queries.user_id=users.id ORDER BY query_time DESC").fetchall()

    return render_template("admin.html", users=users, queries=queries, username=username)
