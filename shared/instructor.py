import json

from flask import Blueprint, flash, redirect, render_template, request, url_for

from shared.db import get_db
from shared.auth import get_session_auth, instructor_required


bp = Blueprint('instructor', __name__, url_prefix="/instructor", template_folder='templates')


@bp.route("/")
@instructor_required
def main():
    db = get_db()
    auth = get_session_auth()

    class_id = auth['lti']['class_id']

    users = db.execute("""
        SELECT
            users.*,
            COUNT(queries.id) AS num_queries,
            SUM(CASE WHEN queries.query_time > date('now', '-7 days') THEN 1 ELSE 0 END) AS num_recent_queries
        FROM users
        JOIN roles ON roles.user_id=users.id
        LEFT JOIN queries ON queries.role_id=roles.id
        WHERE roles.class_id=?
        GROUP BY users.id
    """, [class_id]).fetchall()

    username = None
    if 'username' in request.args:
        username = request.args['username']
        queries = db.execute("SELECT queries.*, users.username FROM queries JOIN users ON queries.user_id=users.id JOIN roles ON queries.role_id=roles.id WHERE users.username=? AND roles.class_id=? ORDER BY query_time DESC", [username, class_id]).fetchall()
    else:
        queries = db.execute("SELECT queries.*, users.username FROM queries JOIN users ON queries.user_id=users.id JOIN roles ON queries.role_id=roles.id WHERE roles.class_id=? ORDER BY query_time DESC", [class_id]).fetchall()

    return render_template("instructor.html", users=users, queries=queries, username=username)


@bp.route("/config")
@instructor_required
def config_form(query_id=None):
    db = get_db()
    auth = get_session_auth()

    class_id = auth['lti']['class_id']

    class_row = db.execute("SELECT * FROM classes WHERE id=?", [class_id]).fetchone()
    class_config = json.loads(class_row['config'])

    return render_template("class_config_form.html", class_id=class_id, class_config=class_config)


@bp.route("/config/set", methods=["POST"])
@instructor_required
def set_config():
    db = get_db()

    class_id = request.form['class_id']
    class_config = {
        'default_lang': request.form['default_lang'],
        'avoid': request.form['avoid'],
    }
    class_config_json = json.dumps(class_config)

    db.execute("UPDATE classes SET config=? WHERE id=?", [class_config_json, class_id])
    db.commit()

    flash("Configuration set!", "success")
    return redirect(url_for(".config_form"))
