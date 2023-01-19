from functools import wraps
from flask import request, redirect, session, url_for

# Constants for use in session dictionary
KEY_AUTH_USER = "__codehelp_logged_in_user"
KEY_AUTH_USERID = "__codehelp_logged_in_userid"
KEY_AUTH_ROLE = "__codehelp_logged_in_role"


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get(KEY_AUTH_USER, "") == "":
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get(KEY_AUTH_ROLE, "") != "admin":
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function
