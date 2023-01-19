from flask import Blueprint, abort, flash, redirect, session, url_for

from pylti.flask import lti

from .db import get_db
from .login import KEY_AUTH_USER, KEY_AUTH_USERID, KEY_AUTH_ROLE


bp = Blueprint('lti', __name__, url_prefix="/lti", template_folder='templates')


# Handles LTI 1.0/1.1 initial request / login
# https://github.com/mitodl/pylti/blob/master/pylti/flask.py
# https://github.com/mitodl/mit_lti_flask_sample
@bp.route("/", methods=['GET', 'POST'])
@lti(request='initial')
def lti_login(lti=lti):
    # sanity checks
    authenticated = session.get("lti_authenticated", False)
    role = session.get("roles", None).lower()
    email = session.get("lis_person_contact_email_primary", None)
    lti_consumer = session.get("oauth_consumer_key", None)
    if not authenticated:
        return abort(403)
    if role not in ["instructor", "student"]:
        return abort(403)
    if email is None or '@' not in email:
        return abort(400)

    # check for and create user if needed
    db = get_db()
    user_row = db.execute(
        "SELECT * FROM users WHERE username=?", [email]
    ).fetchone()

    if not user_row:
        # Register this user
        cur = db.execute("INSERT INTO users(username, role, lti_consumer) VALUES(?, ?, ?)", [email, role, lti_consumer])
        db.commit()
        user_id = cur.lastrowid
    else:
        # Verify the user is coming from the same LTI consumer as when it registered
        if lti_consumer != user_row['lti_consumer']:
            return abort(400)
        # Verify the role is the same
        if role != user_row['role']:
            return abort(400)
        # If all good, fall through
        user_id = user_row['id']

    # Record them as logged in in the session
    session[KEY_AUTH_USER] = email
    session[KEY_AUTH_USERID] = user_id
    session[KEY_AUTH_ROLE] = role

    # Redirect to the app
    flash(f"Welcome, {email}! [{role}]")
    return redirect(url_for("helper.help_form"))
