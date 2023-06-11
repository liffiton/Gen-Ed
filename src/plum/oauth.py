from flask import Blueprint, abort, current_app, flash, redirect, url_for
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
        client_kwargs={'scope': 'openid email profile'},
    )
    _oauth.register(
        name='github',
        api_base_url='https://api.github.com/',
        access_token_url='https://github.com/login/oauth/access_token',
        authorize_url='https://github.com/login/oauth/authorize',
        userinfo_endpoint='https://api.github.com/user',
        client_kwargs={'scope': 'user:email'},
    )


@bp.route('/login/<string:provider_name>')
def login(provider_name):
    client = _oauth.create_client(provider_name)
    if not client:
        abort(404)

    redirect_uri = url_for('.auth', provider_name=provider_name, _external=True)
    return client.authorize_redirect(redirect_uri)


@bp.route('/auth/<string:provider_name>')
def auth(provider_name):
    client = _oauth.create_client(provider_name)
    if not client:
        abort(404)

    client.authorize_access_token()
    user = client.userinfo()

    if not user.get('email'):
        # On Github, email will be null if user does not share email publicly, but we can enumerate
        # their email addresses using the user api and choose the one they have marked 'primary'
        # [https://github.com/authlib/loginpass/blob/master/loginpass/github.py]
        assert provider_name == 'github'
        response = client.get('user/emails')
        response.raise_for_status()
        data = response.json()
        user['email'] = next(item['email'] for item in data if item['primary'])

    user_normed = {
        'email': user.get('email'),
        'full_name': user.get('name'),
        'auth_name': user.get('login'),
        'ext_id': user.get('sub') or user.get('id')   # 'sub' for OpenID Connect (Google); 'id' for Github
    }

    current_app.logger.info(f"SSO login: {provider_name=} {user_normed=}")

    db = get_db()

    provider_row = db.execute("SELECT id FROM auth_providers WHERE name=?", [provider_name]).fetchone()
    provider_id = provider_row['id']

    auth_row = db.execute("SELECT * FROM auth_external WHERE auth_provider=? AND ext_id=?", [provider_id, user_normed['ext_id']]).fetchone()

    if auth_row:
        user_id = auth_row['user_id']
    else:
        # Create a new user.
        # Given 10 tokens by default.
        cur = db.execute(
            "INSERT INTO users (auth_provider, full_name, email, auth_name, query_tokens) VALUES (?, ?, ?, ?, 10)",
            [provider_id, user_normed['full_name'], user_normed['email'], user_normed['auth_name']]
        )
        user_id = cur.lastrowid
        db.execute("INSERT INTO auth_external(user_id, auth_provider, ext_id) VALUES (?, ?, ?)", [user_id, provider_id, user_normed['ext_id']])
        db.commit()

    # get all values in newly inserted row
    user_row = db.execute("SELECT * FROM users WHERE id=?", [user_id]).fetchone()

    # Now, either the user existed or has been created.  Log them in!
    set_session_auth(user_row['id'], user_row['display_name'])
    flash(f"Welcome, {user_row['display_name']}!")
    return redirect('/')
