from flask import Blueprint, abort, redirect, session, url_for

from pylti.flask import lti

from .db import get_db
from .auth import set_session_auth


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

    # sanity checks
    if not authenticated:
        session.clear()
        return abort(403)
    if role not in ["instructor", "student"]:
        session.clear()
        return abort(403)
    if '@' not in email or lti_user_id == "" or lti_consumer == "" or lti_context_id == "" or lti_context_label == "":
        session.clear()
        return abort(400)

    # check for and create user if needed
    lti_id = f"{lti_consumer}_{lti_user_id}_{email}"
    db = get_db()
    user_row = db.execute(
        "SELECT * FROM users WHERE lti_id=?", [lti_id]
    ).fetchone()

    if not user_row:
        # Register this user
        cur = db.execute("INSERT INTO users(username, lti_id, lti_consumer) VALUES(?, ?, ?)", [email, lti_id, lti_consumer])
        db.commit()
        user_id = cur.lastrowid
    else:
        user_id = user_row['id']

    # TODO: add role to DB if not present, set role in session
    # check for and create role if needed
    db = get_db()
    role_row = db.execute(
        "SELECT * FROM roles WHERE user_id=? AND lti_context=?", [user_id, lti_context_label]
    ).fetchone()

    if not role_row:
        # Register this user
        cur = db.execute("INSERT INTO roles(user_id, lti_context, role) VALUES(?, ?, ?)", [user_id, lti_context_label, role])
        db.commit()
        role_id = cur.lastrowid
    else:
        # Role exists in db already.
        # TODO: it's possible the role given via LTI could not match the role saved in the db...
        role_id = role_row['id']

    # Record them as logged in in the session
    role_dict = {
        'id': role_id,
        'context': lti_context_label,
        'role': role,
    }
    set_session_auth(email, user_id, is_admin=False, role=role_dict, clear_session=False)  # don't clear session, contains LTI params

    # Redirect to the app
    #flash(f"Welcome, {email}!")
    return redirect(url_for("helper.help_form"))


@bp.route("debug", methods=['GET'])
@lti(request='session')
def lti_debug(lti=lti):
    return {var: session[var] for var in session}
