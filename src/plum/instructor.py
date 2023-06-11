import csv
import datetime
import io
import json

from flask import Blueprint, flash, make_response, redirect, render_template, request, url_for

from .db import get_db
from .auth import get_session_auth, instructor_required


bp = Blueprint('instructor', __name__, url_prefix="/instructor", template_folder='templates')


def get_queries(class_id, user=None):
    db = get_db()

    where_clause = "WHERE roles.class_id=?"
    params = [class_id]

    if user is not None:
        where_clause += " AND users.email=?"
        params += [user]

    queries = db.execute(f"""
        SELECT
            queries.id,
            users.email,
            queries.query_time,
            queries.language,
            queries.code,
            queries.error,
            queries.issue,
            queries.response_text,
            queries.helpful,
            queries.helpful_emoji
        FROM queries
        JOIN users
            ON queries.user_id=users.id
        JOIN roles
            ON queries.role_id=roles.id
        {where_clause}
        ORDER BY query_time DESC
    """, params).fetchall()

    return queries


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

    user = request.args.get('user', None)

    queries = get_queries(class_id, user)

    return render_template("instructor.html", users=users, queries=queries, user=user)


@bp.route("/queries/csv")
@instructor_required
def get_queries_csv():
    auth = get_session_auth()
    class_id = auth['lti']['class_id']
    queries = get_queries(class_id)

    stringio = io.StringIO()
    writer = csv.writer(stringio)
    writer.writerow(queries[0].keys())  # column headers
    writer.writerows(queries)

    output = make_response(stringio.getvalue())
    class_name = auth['lti']['class_name'].replace(" ","-")
    timestamp = datetime.datetime.now().strftime("%Y%M%d")
    output.headers["Content-Disposition"] = f"attachment; filename={timestamp}_{class_name}_queries.csv"
    output.headers["Content-type"] = "text/csv"

    return output


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
