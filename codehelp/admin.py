from collections import namedtuple

from flask import Blueprint, current_app, render_template, request, send_file

from .db import get_db
from .auth import admin_required


bp = Blueprint('admin', __name__, url_prefix="/admin", template_folder='templates')

Filter = namedtuple('Filter', ('name', 'column', 'value'))


class Filters:
    def __init__(self):
        self._filters = []

    def add_where(self, name, column, value):
        self._filters.append(Filter(name, column, value))

    def make_where(self):
        if not self._filters:
            return "", []
        else:
            return (
                "WHERE " + " AND ".join(f"{f.column}=?" for f in self._filters),
                [f.value for f in self._filters]
            )

    def get_filters(self):
        return self._filters


@bp.route("/")
@admin_required
def main():
    db = get_db()
    classes = db.execute("SELECT classes.*, COUNT(queries.id) AS num_queries FROM classes LEFT JOIN roles ON roles.class_id=classes.id LEFT JOIN queries ON queries.role_id=roles.id GROUP BY classes.id").fetchall()

    filters = Filters()

    if 'class' in request.args:
        filters.add_where("class", "roles.class_id", request.args['class'])

    where_clause, where_params = filters.make_where()
    users = db.execute(f"SELECT users.*, COUNT(queries.id) AS num_queries FROM users LEFT JOIN roles ON roles.user_id=users.id LEFT JOIN queries ON users.id=queries.user_id {where_clause} GROUP BY users.id", where_params).fetchall()

    if 'username' in request.args:
        filters.add_where("user", "users.username", request.args['username'])

    where_clause, where_params = filters.make_where()
    roles = db.execute(f"SELECT roles.*, users.username, COUNT(queries.id) AS num_queries FROM roles LEFT JOIN users ON users.id=roles.user_id LEFT JOIN queries ON roles.id=queries.role_id {where_clause} GROUP BY roles.id", where_params).fetchall()

    if 'role' in request.args:
        filters.add_where("role", "roles.id", request.args['role'])

    where_clause, where_params = filters.make_where()
    queries = db.execute(f"SELECT queries.*, users.username FROM queries JOIN users ON queries.user_id=users.id LEFT JOIN roles ON queries.role_id=roles.id {where_clause} ORDER BY query_time DESC", where_params).fetchall()

    return render_template("admin.html", classes=classes, users=users, roles=roles, queries=queries, filters=filters.get_filters())


@bp.route("/get_db")
@admin_required
def get_db_file():
    return send_file(current_app.config['DATABASE'], as_attachment=True)
