from flask import Blueprint, abort, flash, redirect, url_for
from authlib.integrations.flask_client import OAuth

from .db import get_db
from .auth import set_session_auth


GOOGLE_CONF_URL = 'https://accounts.google.com/.well-known/openid-configuration'


bp = Blueprint('oauth', __name__, url_prefix="/oauth")
_oauth = OAuth()


def init_app(app):
    _oauth.init_app(app)
    _oauth.register(  # automatically loads client ID and secret from app config (see base.py)
        name='google',
        server_metadata_url=GOOGLE_CONF_URL,
        client_kwargs={'scope': 'openid email'},
    )
    _oauth.register(
        name='github',
        api_base_url='https://api.github.com/',
        access_token_url='https://github.com/login/oauth/access_token',
        authorize_url='https://github.com/login/oauth/authorize',
        userinfo_endpoint='https://api.github.com/user',
        client_kwargs={'scope': 'user:email'},
    )


@bp.route('/login/<string:name>')
def login(name):
    client = _oauth.create_client(name)
    if not client:
        abort(404)

    redirect_uri = url_for('.auth', name=name, _external=True)
    return client.authorize_redirect(redirect_uri)


@bp.route('/auth/<string:name>')
def auth(name):
    client = _oauth.create_client(name)
    if not client:
        abort(404)

    client.authorize_access_token()
    user = client.userinfo()

    if not user.get('email'):
        # On Github, email will be null if user does not share email publicly, but we can enumerate
        # their email addresses using the user api and choose the one they have marked 'primary'
        # [https://github.com/authlib/loginpass/blob/master/loginpass/github.py]
        assert name == 'github'
        response = client.get('user/emails')
        response.raise_for_status()
        data = response.json()
        user['email'] = next(item['email'] for item in data if item['primary'])

    assert user['email']
    username = user['email']

    db = get_db()
    user_row = db.execute("SELECT * FROM users WHERE username=?", [username]).fetchone()

    if not user_row:
        # Create a new user.
        # Given 10 tokens by default.
        db.execute("INSERT INTO users (username, query_tokens) VALUES (?, 10)", [username])
        db.commit()
        user_row = db.execute("SELECT * FROM users WHERE username=?", [username]).fetchone()  # simplest way to get all values in newly inserted row

    # Either the user existed or has been created.  Log them in!
    set_session_auth(user_row['id'], user_row['display_name'])
    flash(f"Welcome, {username}!")
    return redirect('/')
