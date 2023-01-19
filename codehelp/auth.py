from functools import wraps
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from .db import get_db

# Constants for use in session dictionary
KEY_AUTH_USER = "__codehelp_logged_in_user"
KEY_AUTH_USERID = "__codehelp_logged_in_userid"
KEY_AUTH_ROLE = "__codehelp_logged_in_role"


bp = Blueprint('auth', __name__, url_prefix="/auth", template_folder='templates')


@bp.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        user_row = db.execute("SELECT * FROM users WHERE username=?", [username]).fetchone()

        if not user_row:
            flash("Invalid username or password.", "warning")
        elif not check_password_hash(user_row['password'], password):
            flash("Invalid username or password.", "warning")
        else:
            # Success!
            session.clear()
            session[KEY_AUTH_USER] = username
            session[KEY_AUTH_USERID] = user_row['id']
            session[KEY_AUTH_ROLE] = user_row['role']
            next_url = request.form['next'] or url_for("helper.help_form")
            flash(f"Welcome, {username}! [{user_row['role']}]")
            return redirect(next_url)

    # we either have a GET request or we fell through the POST login attempt with a failer
    return render_template("login.html")


@bp.route("/logout", methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for(".login"))


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get(KEY_AUTH_USER, "") == "":
            flash("Login required.", "warning")
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get(KEY_AUTH_ROLE, "") != "admin":
            flash("Login required.", "warning")
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function
