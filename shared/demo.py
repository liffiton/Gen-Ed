import datetime as dt
import random

import pytz

from flask import Blueprint, current_app, flash, redirect, render_template, url_for

from shared.db import get_db
from shared.auth import get_session_auth, set_session_auth


bp = Blueprint('demo', __name__, url_prefix="/demo", template_folder='templates')


@bp.route("/<string:demo_name>", methods=['GET'])
def demo_register_user(demo_name):
    # Can't create a demo user if already logged in.
    auth = get_session_auth()
    if auth['username']:
        flash("You are already logged in.", "warning")
        return render_template("error.html")

    # Otherwise, check for valid demo name, create a new demo user, and log this session in to it.
    db = get_db()

    # Check for valid demo
    demo_row = db.execute("SELECT * FROM demo_links WHERE name=?", [demo_name]).fetchone()
    if not demo_row:
        flash("Invalid demo link.", "warning")
        return render_template("error.html")
    else:
        enabled = demo_row['enabled']
        if not enabled:
            flash("Demo link disabled.", "warning")
            return render_template("error.html")

        expiration_date = demo_row['expiration']
        expiration_datetime = dt.datetime.combine(expiration_date, dt.time.max)      # end of the day on the date specified
        expiration_utc = pytz.utc.localize(expiration_datetime)                      # convert "naive" (timezone-less) date into UTC
        now_utc = dt.datetime.now(dt.timezone(dt.timedelta(hours=-12), name='AOE'))  # Anywhere-On-Earth
        if now_utc > expiration_utc:
            flash("Demo link expired.", "warning")
            return render_template("error.html")

    # Find demo username w/ an unused number.
    got_one = False
    while not got_one:
        new_num = random.randrange(10**4, 10**5)  # a new 5-digit number
        new_username = f"demo_{demo_name}_{new_num}"
        check_user = db.execute("SELECT* FROM users WHERE username=?", [new_username]).fetchone()
        got_one = not check_user

    # Register the new user and update the usage count for this demo link
    query_tokens = demo_row['tokens']  # default number of tokens for this demo link
    cur = db.execute("INSERT INTO users(username, query_tokens) VALUES(?, ?)", [new_username, query_tokens])
    db.execute("UPDATE demo_links SET uses=uses+1 WHERE name=?", [demo_name])
    db.commit()
    user_id = cur.lastrowid

    set_session_auth(new_username, user_id, is_admin=False)

    current_app.logger.info(f"Demo login: {demo_name=} {user_id=} {new_username=}")

    # Redirect to the app
    return redirect(url_for("landing"))
