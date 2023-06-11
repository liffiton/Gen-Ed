from flask import Blueprint, abort, current_app, redirect, session, url_for

from pylti.flask import lti

from .db import get_db
from .auth import set_session_auth, AUTH_PROVIDER_LTI


bp = Blueprint('lti', __name__, url_prefix="/lti", template_folder='templates')


# Handles LTI 1.0/1.1 initial request / login
# https://github.com/mitodl/pylti/blob/master/pylti/flask.py
# https://github.com/mitodl/mit_lti_flask_sample
@bp.route("/", methods=['GET', 'POST'])
@lti(request='initial')
def lti_login(lti=lti):
    authenticated = session.get("lti_authenticated", False)
    role = session.get("roles", "").lower()
    email = session.get("lis_person_contact_email_primary", "")
    lti_user_id = session.get("user_id", "")
    lti_consumer = session.get("oauth_consumer_key", "")
    lti_context_id = session.get("context_id", "")
    lti_context_label = session.get("context_label", "")

    current_app.logger.info(f"LTI login: {lti_consumer=} {email=} {lti_user_id=} {role=} {lti_context_id=} {lti_context_label=}")

    # sanity checks
    if not authenticated:
        session.clear()
        return abort(403)
    if '@' not in email or lti_user_id == "" or lti_consumer == "" or lti_context_id == "" or lti_context_label == "":
        session.clear()
        return abort(400)

    current_app.logger.info(f"LTI login: {email=} connected.")

    # Anything that isn't "instructor" becomes "student"
    if role not in ["instructor"]:
        role = "student"

    db = get_db()

    # grab consumer ID (must exist, since the LTI processing must have used it to get here with success)
    consumer_row = db.execute("SELECT id FROM consumers WHERE lti_consumer=?", [lti_consumer]).fetchone()
    lti_consumer_id = consumer_row['id']

    # check for and create class if needed
    class_row = db.execute(
        """
        SELECT * FROM classes WHERE
            classes.lti_consumer_id = ?
            AND classes.lti_context_id = ?
            AND classes.lti_context_label = ?
        """,
        [lti_consumer_id, lti_context_id, lti_context_label]
    ).fetchone()

    if not class_row:
        # Add the class -- will not be usable until an instructor configures it, though.
        cur = db.execute("INSERT INTO classes(lti_consumer_id, lti_context_id, lti_context_label) VALUES(?, ?, ?)", [lti_consumer_id, lti_context_id, lti_context_label])
        db.commit()
        class_id = cur.lastrowid
    else:
        class_id = class_row['id']

    # check for and create user if needed
    lti_id = f"{lti_consumer}_{lti_user_id}_{email}"
    auth_row = db.execute(
        "SELECT * FROM auth_external WHERE auth_provider=? AND ext_id=?", [AUTH_PROVIDER_LTI, lti_id]
    ).fetchone()

    if not auth_row:
        # Register this user
        # 0 tokens, because LTI users should always use a registered consumer's API key
        cur = db.execute("INSERT INTO users(auth_provider, email, query_tokens) VALUES(?, ?, 0)", [AUTH_PROVIDER_LTI, email])
        user_id = cur.lastrowid
        db.execute("INSERT INTO auth_external(user_id, auth_provider, ext_id) VALUES(?, ?, ?)", [user_id, AUTH_PROVIDER_LTI, lti_id])
        db.commit()
    else:
        user_id = auth_row['user_id']

    # check for and create role if needed
    role_row = db.execute(
        "SELECT * FROM roles WHERE user_id=? AND class_id=?", [user_id, class_id]
    ).fetchone()

    if not role_row:
        # Register this user
        cur = db.execute("INSERT INTO roles(user_id, class_id, role) VALUES(?, ?, ?)", [user_id, class_id, role])
        db.commit()
        role_id = cur.lastrowid
    else:
        role_id = role_row['id']

    # Record them as logged in in the session
    lti_dict = {
        'role_id': role_id,
        'role': role,
        'class_id': class_id,
        'class_name': lti_context_label,
        'consumer': lti_consumer,
    }
    user_row = db.execute("SELECT * FROM users WHERE id=?", [user_id]).fetchone()
    set_session_auth(user_id, user_row['display_name'], lti=lti_dict)

    # Redirect to the app
    #flash(f"Welcome, {email}!")
    return redirect(url_for("helper.help_form"))


@bp.route("debug", methods=['GET'])
@lti(request='session')
def lti_debug(lti=lti):
    return {var: session[var] for var in session}
