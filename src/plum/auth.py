from functools import wraps
from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from .db import get_db

# Constants
AUTH_SESSION_KEY = "__codehelp_auth"


def set_session_auth(user_id, display_name, is_admin=False, is_tester=False, class_id=None, class_name=None, role_id=None, role=None):
    session[AUTH_SESSION_KEY] = {
        'user_id': user_id,
        'display_name': display_name,
        'is_admin': is_admin,
        'is_tester': is_tester,
        'class_id': class_id,
        'class_name': class_name,
        'role_id': role_id,
        'role': role,
    }


def set_session_auth_class(class_id, class_name, role_id, role):
    auth = get_session_auth()
    auth['class_id'] = class_id
    auth['class_name'] = class_name
    auth['role_id'] = role_id
    auth['role'] = role
    session[AUTH_SESSION_KEY] = auth


def get_session_auth():
    base = {
        'user_id': None,
        'display_name': None,
        'is_admin': False,
        'is_tester': False,
        'class_id': None,
        'class_name': None,
        'role_id': None,
        'role': None,
    }
    # Get the session auth dict, or an empty dict if it's not there, then
    # "override" any values in 'base' that are defined in the session auth dict.
    auth_dict = base | session.get(AUTH_SESSION_KEY, {})
    return auth_dict


def ext_login_update_or_create(provider_name, user_normed, query_tokens=0):
    """
    For an external authentication login:
      1. Create an account for the user if they do not already have an account (entry in users)
      2. Update the account with user info provided if one does already exist
      3. Get and return the account info for that user

    Parameters
    ----------
    provider_name : str
      Name of the external auth provider: in set {lti, google, github}
    user_normed : dict
      User information.
      Must contain non-null 'ext_id' key; must contain keys 'email', 'full_name', and 'auth_name', and at least one should be non-null.
    query_tokens : int (default 0)
      Number of query tokens to assign to the user *if* creating an account for them (on first login).

    Returns
    -------
    SQLite row object containing the 'users' table row for the now-logged-in user.
    """
    db = get_db()

    provider_row = db.execute("SELECT id FROM auth_providers WHERE name=?", [provider_name]).fetchone()
    provider_id = provider_row['id']

    auth_row = db.execute("SELECT * FROM auth_external WHERE auth_provider=? AND ext_id=?", [provider_id, user_normed['ext_id']]).fetchone()

    if auth_row:
        user_id = auth_row['user_id']
        # Update w/ latest user info (name, email, etc. could conceivably change)
        cur = db.execute(
            "UPDATE users SET full_name=?, email=?, auth_name=? WHERE id=?",
            [user_normed['full_name'], user_normed['email'], user_normed['auth_name'], user_id]
        )
        db.commit()

    else:
        # Create a new user account.
        cur = db.execute(
            "INSERT INTO users (auth_provider, full_name, email, auth_name, query_tokens) VALUES (?, ?, ?, ?, ?)",
            [provider_id, user_normed['full_name'], user_normed['email'], user_normed['auth_name'], query_tokens]
        )
        user_id = cur.lastrowid
        db.execute("INSERT INTO auth_external(user_id, auth_provider, ext_id) VALUES (?, ?, ?)", [user_id, provider_id, user_normed['ext_id']])
        db.commit()

    # get all values in newly updated/inserted row
    user_row = db.execute("SELECT * FROM users WHERE id=?", [user_id]).fetchone()
    return user_row


bp = Blueprint('auth', __name__, url_prefix="/auth", template_folder='templates')


@bp.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        auth_row = db.execute("SELECT * FROM auth_local JOIN users ON auth_local.user_id=users.id WHERE username=?", [username]).fetchone()

        if not auth_row:
            flash("Invalid username or password.", "warning")
        elif not check_password_hash(auth_row['password'], password):
            flash("Invalid username or password.", "warning")
        else:
            # Success!
            set_session_auth(auth_row['id'], auth_row['display_name'], auth_row['is_admin'], auth_row['is_tester'])
            next_url = request.form['next'] or url_for("helper.help_form")
            flash(f"Welcome, {username}!")
            return redirect(next_url)

    # we either have a GET request or we fell through the POST login attempt with a failure
    return render_template("login.html")


@bp.route("/logout", methods=['POST'])
def logout():
    session.clear()  # clear the entire session to be safest here.
    flash("You have been logged out.")
    return redirect(url_for(".login"))


def login_required(f):
    '''Redirect to login on this route if user is not logged in.'''
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = get_session_auth()
        if not auth['user_id']:
            return abort(401)
        return f(*args, **kwargs)
    return decorated_function


def instructor_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = get_session_auth()
        if auth['role'] != "instructor":
            return abort(403)
        return f(*args, **kwargs)
    return decorated_function


def class_config_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = get_session_auth()

        if auth['class_id'] is None:
            # Non-class user
            return f(*args, **kwargs)

        db = get_db()
        class_row = db.execute("SELECT * FROM classes WHERE id=?", [auth['class_id']]).fetchone()
        if class_row['config'] == '{}':
            # Not yet configured
            if auth['role'] == 'instructor':
                flash("This class is not yet configured.  Please configure it so that you and your students can use it.", "danger")
                return redirect(url_for("instructor.config_form"))
            else:
                flash("This class is not yet configured.  Your instructor must configure it before you can use it.", "danger")
                return render_template("error.html")

        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    '''Redirect to login on this route if user is not an admin.'''
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = get_session_auth()
        if not auth['is_admin']:
            flash("Login required.", "warning")
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def tester_required(f):
    '''Return a 404 on this route (hide it, basically) if user is not a tester.'''
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = get_session_auth()
        if not auth['is_tester']:
            return abort(404)
        return f(*args, **kwargs)
    return decorated_function
