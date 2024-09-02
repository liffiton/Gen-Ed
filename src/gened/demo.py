# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import random

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.wrappers.response import Response

from .admin import bp as bp_admin
from .admin import register_admin_link
from .auth import get_auth, set_session_auth_user
from .db import get_db
from .tz import date_is_past

bp = Blueprint('demo', __name__, url_prefix="/demo", template_folder='templates')


@bp.route("/<string:demo_name>", methods=['GET'])
def demo_register_user(demo_name: str) -> str | Response:
    # Can't create a demo user if already logged in.
    auth = get_auth()
    if auth['user_id']:
        flash("You are already logged in.", "warning")
        return render_template("error.html")

    # Otherwise, check for valid demo name, create a new demo user, and log this session in to it.
    db = get_db()

    # Check for valid demo
    demo_row = db.execute("SELECT * FROM demo_links WHERE name=?", [demo_name]).fetchone()
    if not demo_row:
        flash("Invalid demo link.", "warning")
        return render_template("error.html")

    enabled = demo_row['enabled']
    if not enabled:
        flash("Demo link disabled.", "warning")
        return render_template("error.html")

    expiration_date = demo_row['expiration']
    if date_is_past(expiration_date):
        flash("Demo link expired.", "warning")
        return render_template("error.html")

    # Find demo username w/ an unused number.
    got_one = False
    while not got_one:
        new_num = random.randrange(10**4, 10**5)  # a new 5-digit number
        new_username = f"demo_{demo_name}_{new_num}"
        check_user = db.execute("SELECT * FROM users WHERE auth_name=?", [new_username]).fetchone()
        got_one = not check_user

    # Register the new user and update the usage count for this demo link
    query_tokens = demo_row['tokens']  # default number of tokens for this demo link
    cur = db.execute("INSERT INTO users(auth_provider, auth_name, query_tokens) VALUES(3, ?, ?)", [new_username, query_tokens])  # 3 = 'demo' auth provider
    user_id = cur.lastrowid
    db.execute("UPDATE demo_links SET uses=uses+1 WHERE name=?", [demo_name])
    db.commit()

    assert(user_id is not None)
    set_session_auth_user(user_id)

    current_app.logger.info(f"Demo login: {demo_name=} {user_id=} {new_username=}")

    # Redirect to the app
    return redirect(url_for("landing"))


# ### Admin routes ###

@register_admin_link("Demo Links")
@bp_admin.route("/demo_link/")
def demo_link_view() -> str:
    db = get_db()
    demo_links = db.execute("SELECT * FROM demo_links").fetchall()

    return render_template("admin_demo_link.html", demo_links=demo_links)


@bp_admin.route("/demo_link/new")
def demo_link_new() -> str:
    return render_template("demo_link_form.html")


@bp_admin.route("/demo_link/<int:demo_id>")
def demo_link_form(demo_id: int) -> str:
    db = get_db()
    demo_link_row = db.execute("SELECT * FROM demo_links WHERE id=?", [demo_id]).fetchone()
    demo_link_url = f"/demo/{demo_link_row['name']}"
    return render_template("demo_link_form.html", demo_link=demo_link_row, demo_link_url=demo_link_url)


@bp_admin.route("/demo_link/update", methods=['POST'])
def demo_link_update() -> Response:
    db = get_db()

    demo_link_id = request.form.get("demo_link_id", type=int)
    enabled = 1 if 'enabled' in request.form else 0

    if demo_link_id is None:
        # Adding a new demo_link
        cur = db.execute("INSERT INTO demo_links (name, expiration, tokens, enabled) VALUES (?, ?, ?, ?)",
                         [request.form['name'], request.form['expiration'], request.form['tokens'], enabled])
        demo_link_id = cur.lastrowid
        db.commit()

    else:
        # Updating
        cur = db.execute("UPDATE demo_links SET expiration=?, tokens=?, enabled=? WHERE id=?",
                         [request.form['expiration'], request.form['tokens'], enabled, demo_link_id])
        db.commit()
        flash("Demo link updated.")

    return redirect(url_for(".demo_link_form", demo_id=demo_link_id))
