from functools import wraps
from flask import Blueprint, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from .db import get_db

# Constants
AUTH_SESSION_KEY = "__plum_auth"


def set_session_auth(user_id, display_name, is_admin=False, is_tester=False, role_id=None):
    session[AUTH_SESSION_KEY] = {
        'user_id': user_id,
        'display_name': display_name,
        'is_admin': is_admin,
        'is_tester': is_tester,
        'role_id': role_id,
    }


def set_session_auth_role(role_id):
    auth = session[AUTH_SESSION_KEY]
    auth['role_id'] = role_id
    session[AUTH_SESSION_KEY] = auth


def _get_auth_from_session():
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

    db = get_db()

    if auth_dict['user_id']:
        # Get the auth provider
        provider_row = db.execute("""
            SELECT auth_providers.name
            FROM users
            JOIN auth_providers ON auth_providers.id=users.auth_provider
            WHERE users.id=?
        """, [auth_dict['user_id']]).fetchone()
        auth_dict['auth_provider'] = provider_row['name']

    if auth_dict['role_id']:
        # Check the database for the current role (may be changed by another user)
        # and populate class/role information.
        # Uses WHERE active=1 to only allow active roles.
        role_row = db.execute("""
            SELECT
                roles.class_id,
                classes.name,
                roles.role
            FROM roles
            JOIN classes ON classes.id=roles.class_id
            WHERE roles.id=? AND roles.active=1
        """, [auth_dict['role_id']]).fetchone()
        if role_row:
            auth_dict = auth_dict | {
                'class_id': role_row['class_id'],
                'class_name': role_row['name'],
                'role': role_row['role'],
            }
        else:
            # drop the role_id we supposedly had
            auth_dict['role_id'] = None

    return auth_dict


def get_auth():
    if 'auth' not in g:
        g.auth = _get_auth_from_session()

    return g.auth


def ext_login_update_or_create(provider_name, user_normed, query_tokens=0):
    """
    For an external authentication login:
      1. Create an account for the user if they do not already have an account (entry in users)
      2. Update the account with user info provided if one does already exist
      3. Get and return the account info for that user

    Parameters
    ----------
    provider_name : str
      Name of the external auth provider: in set {lti, google, github, microsoft}
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
            return redirect(next_url)

    # we either have a GET request or we fell through the POST login attempt with a failure
    next_url = request.args.get('next', '')
    return render_template("login.html", next_url=next_url)


@bp.route("/logout", methods=['POST'])
def logout():
    session.clear()  # clear the entire session to be safest here.
    flash("You have been logged out.")
    return redirect(url_for(".login"))


def login_required(f):
    '''Redirect to login on this route if user is not logged in.'''
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = get_auth()
        if not auth['user_id']:
            flash("Login required.", "warning")
            return redirect(url_for('auth.login', next=request.full_path))
        return f(*args, **kwargs)
    return decorated_function


def instructor_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = get_auth()
        if auth['role'] != "instructor":
            return abort(403)
        return f(*args, **kwargs)
    return decorated_function


def class_config_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = get_auth()
        class_id = auth['class_id']

        if class_id is None:
            # No active class, no problem
            return f(*args, **kwargs)

        # Otherwise, there's an active class, so we require it to have a non-empty configuration.
        db = get_db()
        class_row = db.execute("SELECT * FROM classes WHERE id=?", [class_id]).fetchone()
        if class_row['config'] == '{}':
            # Not yet configured
            if auth['role'] == 'instructor':
                flash("This class is not yet configured.  Please configure it so that you and your students can use it.", "danger")
                return redirect(url_for("instructor.config_form"))
            else:
                flash("This class is not yet configured.  Your instructor must configure it before you can use it.", "danger")
                return render_template("error.html")
        # And it must be active
        if not class_row['enabled']:
            flash("The current class is archived or disabled.  New requests cannot be made.", "warning")
            return render_template("error.html")

        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    '''Redirect to login on this route if user is not an admin.'''
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = get_auth()
        if not auth['is_admin']:
            flash("Login required.", "warning")
            return redirect(url_for('auth.login', next=request.full_path))
        return f(*args, **kwargs)
    return decorated_function


def tester_required(f):
    '''Return a 404 on this route (hide it, basically) if user is not a tester.'''
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = get_auth()
        if not auth['is_tester']:
            return abort(404)
        return f(*args, **kwargs)
    return decorated_function
