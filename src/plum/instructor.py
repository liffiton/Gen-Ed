import csv
import datetime as dt
import io
import json

from flask import Blueprint, flash, make_response, redirect, render_template, request, url_for

from .db import get_db
from .auth import get_auth, instructor_required
from .tz import date_is_past


bp = Blueprint('instructor', __name__, url_prefix="/instructor", template_folder='templates')


def get_queries(class_id, user=None):
    db = get_db()

    where_clause = "WHERE roles.class_id=?"
    params = [class_id]

    if user is not None:
        where_clause += " AND users.id=?"
        params += [user]

    queries = db.execute(f"""
        SELECT
            queries.id,
            users.display_name,
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
    auth = get_auth()

    class_id = auth['class_id']

    users = db.execute("""
        SELECT
            users.id,
            users.display_name,
            users.email,
            users.auth_name,
            roles.id AS role_id,
            roles.active,
            auth_providers.name AS auth_provider,
            COUNT(queries.id) AS num_queries,
            SUM(CASE WHEN queries.query_time > date('now', '-7 days') THEN 1 ELSE 0 END) AS num_recent_queries
        FROM users
        LEFT JOIN auth_providers ON users.auth_provider=auth_providers.id
        JOIN roles ON roles.user_id=users.id
        LEFT JOIN queries ON queries.role_id=roles.id
        WHERE roles.class_id=?
        GROUP BY users.id
        ORDER BY display_name
    """, [class_id]).fetchall()

    user_id = request.args.get('user', None)
    if user_id:
        user_display_row = db.execute("SELECT display_name FROM users WHERE id=?", [user_id]).fetchone()
        user = user_display_row[0]
    else:
        user = None

    queries = get_queries(class_id, user_id)

    return render_template("instructor.html", users=users, queries=queries, user=user)


@bp.route("/queries/csv")
@instructor_required
def get_queries_csv():
    auth = get_auth()
    class_id = auth['class_id']
    queries = get_queries(class_id)

    stringio = io.StringIO()
    writer = csv.writer(stringio)
    writer.writerow(queries[0].keys())  # column headers
    writer.writerows(queries)

    output = make_response(stringio.getvalue())
    class_name = auth['class_name'].replace(" ","-")
    timestamp = dt.datetime.now().strftime("%Y%M%d")
    output.headers["Content-Disposition"] = f"attachment; filename={timestamp}_{class_name}_queries.csv"
    output.headers["Content-type"] = "text/csv"

    return output


@bp.route("/config")
@instructor_required
def config_form():
    db = get_db()
    auth = get_auth()

    class_id = auth['class_id']

    class_row = db.execute("""
        SELECT classes.id, classes.enabled, classes.config, classes_user.link_ident, classes_user.link_reg_expires, classes_user.openai_key
        FROM classes
        LEFT JOIN classes_user
          ON classes.id = classes_user.class_id
        WHERE classes.id=?
    """, [class_id]).fetchone()
    class_config = json.loads(class_row['config'])

    expiration_date = class_row['link_reg_expires']
    if expiration_date is None:
        link_reg_state = None  # not a user-created class
    elif date_is_past(expiration_date):
        link_reg_state = "disabled"
    elif expiration_date == dt.date.max:
        link_reg_state = "enabled"
    else:
        link_reg_state = "date"

    return render_template("class_config_form.html", class_row=class_row, link_reg_state=link_reg_state, class_config=class_config)


@bp.route("/user_class/set", methods=["POST"])
@instructor_required
def set_user_class_setting():
    db = get_db()
    auth = get_auth()

    # only trust class_id from auth, not from user
    class_id = auth['class_id']

    if 'clear_openai_key' in request.form:
        db.execute("UPDATE classes_user SET openai_key='' WHERE class_id=?", [class_id])
        db.commit()
        flash("Class API key cleared.", "success")

    elif 'set_openai_key' in request.form:
        db.execute("UPDATE classes_user SET openai_key=? WHERE class_id=?", [request.form['openai_key'], class_id])
        db.commit()
        flash("Class API key set.", "success")

    else:
        if 'link_reg_active_present' in request.form:
            # only present for user classes, not LTI
            link_reg_active = request.form['link_reg_active']
            if link_reg_active == "disabled":
                new_date = dt.date.min
            elif link_reg_active == "enabled":
                new_date = dt.date.max
            else:
                new_date = request.form['link_reg_expires']
            db.execute("UPDATE classes_user SET link_reg_expires=? WHERE class_id=?", [new_date, class_id])
        class_enabled = 1 if 'class_enabled' in request.form else 0
        db.execute("UPDATE classes SET enabled=? WHERE id=?", [class_enabled, class_id])
        db.commit()
        flash("Class updated.", "success")

    return redirect(url_for(".config_form"))


@bp.route("/role/set_active/", methods=["POST"])
@bp.route("/role/set_active/<int:role_id>/<int:active>", methods=["POST"])
@instructor_required
def set_role_active(role_id, active):
    db = get_db()
    auth = get_auth()

    # class_id should be redundant w/ role_id, but without it, an instructor
    # could potentially deactivate a role in someone else's class.
    # only trust class_id from auth, not from user
    class_id = auth['class_id']

    db.execute("UPDATE roles SET active=? WHERE id=? AND class_id=?", [active, role_id, class_id])
    db.commit()

    return "okay"


# TODO: Move this to app-specific module... #
@bp.route("/config/set", methods=["POST"])
@instructor_required
def set_config():
    db = get_db()
    auth = get_auth()

    # only trust class_id from auth, not from user
    class_id = auth['class_id']

    class_config = {
        'default_lang': request.form['default_lang'],
        'avoid': request.form['avoid'],
    }
    class_config_json = json.dumps(class_config)

    db.execute("UPDATE classes SET config=? WHERE id=?", [class_config_json, class_id])
    db.commit()

    flash("Configuration set!", "success")
    return redirect(url_for(".config_form"))
