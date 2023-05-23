from functools import wraps
from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from .db import get_db

# Constants for use in session dictionary
AUTH_SESSION_KEY = "__codehelp_auth"


def set_session_auth(username, user_id, is_admin, lti=None):
    session[AUTH_SESSION_KEY] = {
        'username': username,
        'user_id': user_id,
        'is_admin': is_admin,
        'lti': lti,
    }


def get_session_auth():
    base = {
        'username': None,
        'user_id': None,
        'is_admin': False,
        'lti': None,
    }
    # Get the session auth dict, or an empty dict if it's not there, then
    # "override" any values in 'base' that are defined in the session auth dict.
    auth_dict = base | session.get(AUTH_SESSION_KEY, {})
    return auth_dict


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
            set_session_auth(username, user_row['id'], user_row['is_admin'])
            next_url = request.form['next'] or url_for("helper.help_form")
            flash(f"Welcome, {username}!")
            return redirect(next_url)

    # we either have a GET request or we fell through the POST login attempt with a failer
    return render_template("login.html")


@bp.route("/logout", methods=['POST'])
def logout():
    session.clear()  # clear the entire session to be safest here.
    flash("You have been logged out.")
    return redirect(url_for(".login"))


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = get_session_auth()
        if not auth['username']:
            return abort(401)
        return f(*args, **kwargs)
    return decorated_function


def instructor_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = get_session_auth()
        if not auth['lti'] or auth['lti']['role'] != "instructor":
            return abort(403)
        return f(*args, **kwargs)
    return decorated_function


def class_config_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = get_session_auth()
        assert 'lti' in auth   # this requires login, so @login_required must be used before it

        if auth['lti'] is None:
            # Non-class user
            return f(*args, **kwargs)

        db = get_db()
        class_row = db.execute("SELECT * FROM classes WHERE id=?", [auth['lti']['class_id']]).fetchone()
        if class_row['config'] == '{}':
            # Not yet configured
            if auth['lti']['role'] == 'instructor':
                flash("This class is not yet configured.  Please configure it so that you and your students can use the tool.", "danger")
                return redirect(url_for("instructor.config_form"))
            else:
                flash("This class is not yet configured.  Your instructor must configure it before you can use this tool.", "danger")
                return render_template("error.html")

        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = get_session_auth()
        if not auth['is_admin']:
            flash("Login required.", "warning")
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def uses_token(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = get_session_auth()
        db = get_db()
        user_row = db.execute("SELECT query_tokens FROM users WHERE id=?", [auth['user_id']]).fetchone()
        tokens = user_row['query_tokens']
        if tokens is not None:
            if tokens == 0:
                flash("You have used all of your query tokens.  Please use the contact form at the bottom of the page if you want to continue using CodeHelp.", "warning")
                return redirect(url_for('helper.help_form'))
            else:
                db.execute("UPDATE users SET query_tokens=query_tokens-1 WHERE id=?", [auth['user_id']])
                db.commit()
        return f(*args, **kwargs)
    return decorated_function
