from flask import Blueprint, current_app, render_template, request, send_file

from .db import get_db
from .auth import admin_required


bp = Blueprint('admin', __name__, url_prefix="/admin", template_folder='templates')


@bp.route("/")
@admin_required
def main():
    db = get_db()
    classes = db.execute("SELECT classes.*, COUNT(queries.id) AS num_queries FROM classes LEFT JOIN roles ON roles.class_id=classes.id LEFT JOIN queries ON queries.role_id=roles.id GROUP BY classes.id").fetchall()
    users = db.execute("SELECT users.*, COUNT(queries.id) AS num_queries FROM users LEFT JOIN queries ON users.id=queries.user_id GROUP BY users.id").fetchall()
    roles = db.execute("SELECT roles.*, users.username, COUNT(queries.id) AS num_queries FROM roles LEFT JOIN users ON users.id=roles.user_id LEFT JOIN queries ON roles.id=queries.role_id GROUP BY roles.id").fetchall()

    username = None
    role = None
    if 'username' in request.args:
        username = request.args['username']
        queries = db.execute("SELECT queries.*, users.username FROM queries JOIN users ON queries.user_id=users.id WHERE users.username=? ORDER BY query_time DESC", [username]).fetchall()
    elif 'role' in request.args:
        role = request.args['role']
        queries = db.execute("SELECT queries.*, users.username FROM queries JOIN users ON queries.user_id=users.id WHERE queries.role_id=? ORDER BY query_time DESC", [role]).fetchall()
    else:
        queries = db.execute("SELECT queries.*, users.username FROM queries JOIN users ON queries.user_id=users.id ORDER BY query_time DESC").fetchall()

    return render_template("admin.html", classes=classes, users=users, roles=roles, queries=queries, username=username, role=role)


@bp.route("/get_db")
@admin_required
def get_db_file():
    return send_file(current_app.config['DATABASE'], as_attachment=True)
