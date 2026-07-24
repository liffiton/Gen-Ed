# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

"""General class management and access control.

This module handles class-related operations available to all users, including:
- Class creation and configuration
- Class access and registration
- Role switching between classes
- Basic class state management

For instructor-specific operations, see instructor.py.
"""

import datetime as dt
from hashlib import blake2b

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.wrappers.response import Response

from .access import login_required
from .auth import get_auth, set_session_auth_class, set_session_auth_user
from .class_config.access_links import AccessLink, v2_check_hash, v2_generate_new_key
from .component_registry import get_navbar_components
from .db import get_db
from .llm import LLM, with_llm
from .redir import safe_redirect_next

bp = Blueprint('classes', __name__, template_folder='templates')


@bp.route("/home")
@login_required
@with_llm(spend_token=False)  # get information on the selected LLM, tokens remaining
def class_home(llm: LLM) -> Response | str:
    components = get_navbar_components()

    if len(components) == 1 and (endpoint := components[0].main_endpoint) is not None:
        # only one component; redirect straight to it
        return redirect(url_for(endpoint))

    return render_template("class_home.html", llm=llm, components=components)


def get_or_create_lti_class(lti_consumer_id: int, lti_context_id: str, class_name: str) -> int:
    """
    Get a class (by id) for a given LTI connection, creating the class
    if it does not already exist.

    Parameters
    ----------
    lti_consumer_id : int
      row ID for an LTI consumer (in table lti_consumers)
    lti_context_id : str
      class identifier from the LMS
    class_name : str
      class name from the LMS

    Returns
    -------
    int: class ID (row primary key) for the new or existing class.
    """
    db = get_db()

    class_row = db.execute("""
        SELECT classes.id, classes.name
        FROM classes
        JOIN classes_lti
          ON classes.id=classes_lti.class_id
        WHERE classes_lti.lti_consumer_id=?
          AND classes_lti.lti_context_id=?
    """, [lti_consumer_id, lti_context_id]).fetchone()

    if class_row:
        # update class name if it has changed on the remote
        if class_row['name'] != class_name:
            db.execute("UPDATE classes SET name=? WHERE id=?", [class_name, class_row['id']])
            db.commit()

        assert isinstance(class_row['id'], int)
        return class_row['id']

    else:
        cur = db.execute("INSERT INTO classes (name) VALUES (?)", [class_name])
        class_id = cur.lastrowid
        assert class_id is not None
        db.execute(
            "INSERT INTO classes_lti (class_id, lti_consumer_id, lti_context_id) VALUES (?, ?, ?)",
            [class_id, lti_consumer_id, lti_context_id]
        )
        db.commit()

        current_app.logger.info(f"New class (LTI): {class_name} ({class_id})")

        return class_id


def create_user_class(user_id: int, class_name: str, llm_api_key: str | None = None) -> int:
    """
    Create a user class.  Assign the given user an 'instructor' role in it.

    Parameters
    ----------
    user_id : int
      id of the user creating the course -- will be given the instructor role
    class_name : str
      class name from the user
    llm_api_key : str | None
      LLM API key from the user.  This is not strictly required, as a class can
      exist with no key assigned, but it is clearer for the user if we require
      an API key up front.

    Returns
    -------
    int: class ID (row primary key) for the new class.
    """
    db = get_db()

    # generate a new, unique, unguessable link key
    # currently on version 2 of this feature
    link_key = v2_generate_new_key()

    cur = db.execute("INSERT INTO classes (name) VALUES (?)", [class_name])
    class_id = cur.lastrowid
    assert class_id is not None
    # Get default model ID - first active system model
    model_id = db.execute(
        "SELECT id FROM models WHERE active AND scope='system' ORDER BY id ASC LIMIT 1"
    ).fetchone()['id']

    db.execute(
        "INSERT INTO classes_user (class_id, creator_user_id, link_key, llm_api_key, link_reg_expires, model_id) VALUES (?, ?, ?, ?, ?, ?)",
        [class_id, user_id, link_key, llm_api_key, dt.date.min, model_id]
    )
    db.execute(
        "INSERT INTO roles (user_id, class_id, role) VALUES (?, ?, ?)",
        [user_id, class_id, 'instructor']
    )
    db.commit()

    current_app.logger.info(f"New class (user): {class_name} ({class_id})")

    return class_id


def switch_class(class_id: int | None) -> bool:
    '''Switch the current user to their role in the given class.
       Or switch them to no class / no role if class_id is None.

       Admin users can switch to any class.

    Returns bool: True if user has an active role in that class and switch succeeds.
                  False otherwise.
    '''
    auth = get_auth()

    # admins can access any class, but we don't bother setting last_class_id for them
    if auth.is_admin:
        set_session_auth_class(class_id)
        return True

    user_id = auth.user_id
    db = get_db()

    if class_id:
        # check for a valid role in the new class
        row = db.execute("""
            SELECT
                roles.id AS role_id,
                roles.role,
                classes.id AS class_id,
                classes.name AS class_name
            FROM roles
            LEFT JOIN classes ON roles.class_id=classes.id
            WHERE roles.user_id=? AND roles.active=1 AND classes.id=?
        """, [user_id, class_id]).fetchone()

        if not row:
            # no valid row found; change nothing and return failure
            return False

        # otherwise, we can continue with this class_id

    set_session_auth_class(class_id)
    # record as user's latest active class
    db.execute("UPDATE users SET last_class_id=? WHERE users.id=?", [class_id, user_id])
    db.commit()
    return True


@bp.route("/switch/")  # just for url_for feeding js (doesn't know the id yet)
@bp.route("/switch/<int:class_id>")
@login_required
def switch_class_handler(class_id: int) -> Response:
    switch_class(class_id)

    auth = get_auth()
    if auth.cur_class is None:
        redir_endpoint = "profile.main"
    elif auth.cur_class.role == "instructor":
        redir_endpoint = "class_config.base.config_form"
    else:
        redir_endpoint = "classes.class_home"

    return safe_redirect_next(default_endpoint=redir_endpoint)


@bp.route("/leave/")
@login_required
def leave_class_handler() -> Response:
    switch_class(None)
    return redirect(url_for("profile.main"))


@bp.route("/create/", methods=['POST'])
@login_required
def create_class() -> Response:
    auth = get_auth()
    user_id = auth.user_id
    assert user_id is not None

    class_name = request.form['class_name']
    llm_api_key = request.form['llm_api_key']

    class_id = create_user_class(user_id, class_name, llm_api_key)
    success = switch_class(class_id)
    assert success

    return redirect(url_for("class_config.base.config_form"))


# Not using @login_required here because we may need to redirect to anon. login specifically
@bp.route("/access/<string:class_ident>")
def access_class_v1(class_ident: str) -> str | Response:
    db = get_db()

    # Get the class info
    key = f"v1.{class_ident}"
    class_row = db.execute("""
        SELECT classes.id, classes.name, classes_user.link_key, classes_user.link_reg_expires, classes_user.link_anon_login
        FROM classes
        JOIN classes_user
          ON classes.id = classes_user.class_id
        WHERE classes_user.link_key = ?
    """, [key]).fetchone()

    if not class_row:
        abort(404)

    # row exists with that ident: continue
    link = AccessLink.from_row(class_row)
    return _join_class(link)


@bp.route("/access/<int:class_id>/<string:hash_val>")
@bp.route("/access/<int:class_id>/<int:counter>/<string:hash_val>")
def access_class_v2(class_id: int, hash_val: str, counter: int | None = None) -> str | Response:
    db = get_db()

    # Get the class info
    class_row = db.execute("""
        SELECT classes.id, classes.name, classes_user.link_key, classes_user.link_reg_expires, classes_user.link_anon_login
        FROM classes
        JOIN classes_user
          ON classes.id = classes_user.class_id
        WHERE classes_user.class_id = ?
    """, [class_id]).fetchone()

    if not class_row:
        abort(404)

    link = AccessLink.from_row(class_row)

    # verify the hash
    valid = v2_check_hash(link.key, hash_val, counter)
    if not valid:
        abort(404)

    # hash is correct: continue
    return _join_class(link, counter)


def _join_class(link: AccessLink, counter: int | None = None) -> str | Response:
    '''Join a class or just login/access it.

    If the user already has a role in the class, just access it.
    Otherwise, check if the link and class are both enabled, and if so,
    add this user to the class.
    '''
    db = get_db()
    auth = get_auth()

    class_id = link.class_id

    # first, check if the user is logged in and already has a role in the class
    if auth.user:
        role_row = db.execute("SELECT * FROM roles WHERE class_id=? AND user_id=?", [class_id, auth.user_id]).fetchone()

        if role_row:
            # user already has a role, but it may not be active
            success = switch_class(class_id)
            if not success:
                abort(403)
            else:
                return redirect(url_for(current_app.config['DEFAULT_LOGIN_ENDPOINT']))

        # logged in (but no existing role) conflicts with no-login links
        if counter is not None:
            flash("No-login links cannot be used when already logged in.", "warning")
            return render_template("error.html")

    # no existing active role: for all other cases, we're registering,
    # so only proceed if registration is enabled
    if link.reg_state == 'disabled':
        flash("Registration is not active for this class.  Please contact the instructor for assistance.", "warning")
        return render_template("error.html")

    if auth.user:
        # user must be logged in but not yet enrolled in the class,
        # so enroll them and switch to the class
        return _enroll_and_switch(class_id)

    if link.anon_login and counter is not None:
        # no-login counter-based link:
        #  1) create new user if doesn't already exist
        #  2) log session in as that user
        #  3) enroll them and switch to the class
        _activate_nologin_user(class_id, link.key, counter)
        return _enroll_and_switch(class_id)
    else:
        # either normal login or normal anon registration;
        # redir to login with the correct argument
        flash(f"Please log in to access class '{link.class_name}'")
        anon = 1 if link.anon_login else None
        return redirect(url_for('auth.login', anon=anon, next=request.full_path))


def _activate_nologin_user(class_id: int, link_key: str, counter: int) -> None:
    """ Activate a nologin user, creating it first if needed.

    Derives a short hash from the link key so that regenerating the key
    produces fresh accounts rather than reconnecting to old ones.

    Parameters
    ----------
    class_id : int
      id of the class in which to create them -- will be included in the username
    link_key: str
      the current v2 link key for the class, used to derive a key-specific hash
    counter: int
      counter to differentiate users within the class -- will be included in the username
    """
    db = get_db()
    assert get_auth().user is None

    key_secret = link_key[3:]
    key_hash = blake2b(key_secret.encode(), digest_size=3).hexdigest()
    username = f"user{key_hash}_{class_id}_{counter}"

    provider_row = db.execute("SELECT id FROM auth_providers WHERE name='nologin'").fetchone()
    nologin_provider_id = provider_row['id']

    user_row = db.execute("SELECT * FROM users WHERE auth_name=? AND auth_provider=?", [username, nologin_provider_id]).fetchone()
    if user_row:
        user_id = user_row['id']
    else:
        cur = db.execute("INSERT INTO users(auth_provider, auth_name, query_tokens) VALUES(?, ?, 0)", [nologin_provider_id, username])
        user_id = cur.lastrowid
        db.commit()

    assert user_id is not None
    set_session_auth_user(user_id)


def _enroll_and_switch(class_id: int) -> Response:
    """ Enroll the current user in the given class, and switch into that class. """
    db = get_db()
    auth = get_auth()
    assert auth.user is not None

    # OR IGNORE: proceed even if the role already exists (UNIQUE constraint violated)
    db.execute(
        "INSERT OR IGNORE INTO roles (user_id, class_id, role) VALUES (?, ?, ?)",
        [auth.user_id, class_id, 'student']
    )
    db.commit()

    # user may already has a role that is disabled; check for switch success
    success = switch_class(class_id)
    if not success:
        abort(403)

    return redirect(url_for(current_app.config['DEFAULT_LOGIN_ENDPOINT']))
